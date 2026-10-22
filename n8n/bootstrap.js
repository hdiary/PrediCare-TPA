const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn, spawnSync } = require('node:child_process');

const n8nData = '/home/node/.n8n';
const dbFile = path.join(n8nData, 'database.sqlite');
const workflowId = 'lCNZNFqhg8cnaaGa';
const credentialId = '8dbb9350-7493-4b15-a92c-d9ed69b0c312';
const workflowMarker = path.join(n8nData, '.predicare-workflow-imported');

// Commandes ponctuelles (import, publish) : on attend la fin
function runN8n(args) {
  const result = spawnSync('n8n', args, { stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`n8n ${args[0]} failed with status ${result.status}`);
  }
}

// Démarrage final : processus long, avec relais des signaux (docker stop propre)
function startN8n() {
  const child = spawn('n8n', ['start'], { stdio: 'inherit' });
  for (const sig of ['SIGTERM', 'SIGINT']) {
    process.on(sig, () => child.kill(sig));
  }
  child.on('exit', (code) => process.exit(code ?? 0));
  child.on('error', (err) => {
    console.error(err);
    process.exit(1);
  });
}

// Utilitaire : sqlite3 en promesse
function dbGet(database, sql, params = []) {
  return new Promise((resolve, reject) => {
    database.get(sql, params, (err, row) => (err ? reject(err) : resolve(row)));
  });
}

function dbClose(database) {
  return new Promise((resolve) => database.close(() => resolve()));
}

async function main() {
  if (!process.env.N8N_DB_PASSWORD) {
    throw new Error('N8N_DB_PASSWORD must be set in .env');
  }

  // Premier démarrage : la base n'existe pas encore, n8n la créera
  if (!fs.existsSync(dbFile)) {
    console.log(
      "Premier démarrage : ouvrez http://localhost:5678, créez le compte owner, " +
      'puis lancez : docker compose restart n8n',
    );
    startN8n();
    return;
  }

  // Localiser le driver SQLite embarqué dans n8n
  const pnpmModules = '/usr/local/lib/node_modules/n8n/node_modules/.pnpm';
  const sqlitePackage = fs
    .readdirSync(pnpmModules)
    .find((name) => name.startsWith('sqlite3@'));
  if (!sqlitePackage) throw new Error("Could not locate n8n's SQLite driver");
  process.env.NODE_PATH = path.join(pnpmModules, sqlitePackage, 'node_modules');
  require('node:module').Module._initPaths();
  const sqlite3 = require('sqlite3');

  const database = new sqlite3.Database(dbFile, sqlite3.OPEN_READONLY);

  let owner;
  let existingCredential;
  try {
    owner = await dbGet(
      database,
      "SELECT id FROM user WHERE roleSlug = 'global:owner' AND disabled = 0 LIMIT 1",
    );
    if (owner) {
      existingCredential = await dbGet(
        database,
        'SELECT id FROM credentials_entity WHERE id = ?',
        [credentialId],
      );
    }
  } catch (err) {
    // Base présente mais pas encore initialisée (migrations n8n non faites)
    console.log(`Base n8n non prête (${err.code || err.message}), démarrage simple.`);
  } finally {
    await dbClose(database);
  }

  if (!owner) {
    console.log(
      'Compte owner n8n absent : créez-le, puis relancez : docker compose restart n8n',
    );
    startN8n();
    return;
  }

  // Credential PostgreSQL
  if (existingCredential) {
    console.log('PrediCare PostgreSQL credential is already provisioned.');
  } else {
    const temporaryDirectory = fs.mkdtempSync(
      path.join(os.tmpdir(), 'predicare-n8n-credential-'),
    );
    const credentialFile = path.join(temporaryDirectory, 'postgres.json');
    const credential = {
      id: credentialId,
      name: 'PrediCare PostgreSQL alertes',
      type: 'postgres',
      data: {
        host: 'db',
        database: process.env.POSTGRES_DB || 'predicare',
        user: 'n8n_alert',
        password: process.env.N8N_DB_PASSWORD,
        port: 5432,
        maxConnections: 5,
        allowUnauthorizedCerts: false,
        ssl: 'disable',
        sshTunnel: false,
      },
    };

    try {
      fs.writeFileSync(credentialFile, JSON.stringify([credential]), {
        mode: 0o600,
      });
      runN8n([
        'import:credentials',
        `--input=${credentialFile}`,
        `--userId=${owner.id}`,
      ]);
    } finally {
      fs.rmSync(temporaryDirectory, { recursive: true, force: true });
    }
  }

  // Workflow (une seule fois)
  if (!fs.existsSync(workflowMarker)) {
    runN8n(['import:workflow', '--input=/workflows/alerte_fraude.json']);
    runN8n(['publish:workflow', `--id=${workflowId}`]);
    fs.writeFileSync(workflowMarker, 'imported\n');
  }

  startN8n();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});