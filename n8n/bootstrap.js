const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const n8nData = '/home/node/.n8n';
const workflowId = 'lCNZNFqhg8cnaaGa';
const credentialId = '8dbb9350-7493-4b15-a92c-d9ed69b0c312';
const workflowMarker = path.join(n8nData, '.predicare-workflow-imported');
const databasePath = path.join(n8nData, 'database.sqlite');

function runN8n(args) {
  const result = spawnSync('n8n', args, { stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`n8n ${args[0]} failed with status ${result.status}`);
  }
}

if (!process.env.N8N_DB_PASSWORD) {
  throw new Error('N8N_DB_PASSWORD must be set in .env');
}

const pnpmModules = '/usr/local/lib/node_modules/n8n/node_modules/.pnpm';
const sqlitePackage = fs
  .readdirSync(pnpmModules)
  .find((name) => name.startsWith('sqlite3@'));
if (!sqlitePackage) throw new Error("Could not locate n8n's SQLite driver");
process.env.NODE_PATH = path.join(pnpmModules, sqlitePackage, 'node_modules');
require('node:module').Module._initPaths();
const sqlite3 = require('sqlite3');
if (!fs.existsSync(databasePath)) {
  console.log('Initialize the n8n database and owner account, then restart n8n.');
  runN8n(['start']);
  process.exit(0);
}

const database = new sqlite3.Database(
  `file:${databasePath}?mode=ro`,
  sqlite3.OPEN_READONLY | sqlite3.OPEN_URI,
);

database.get(
  "SELECT id FROM user WHERE roleSlug = 'global:owner' AND disabled = 0 LIMIT 1",
  (error, owner) => {
    if (error) throw error;
    if (!owner) {
      database.close();
      console.log(
        'Create the n8n owner account, then restart n8n to provision its PostgreSQL credential.',
      );
      runN8n(['start']);
      return;
    }

    database.get(
      'SELECT id FROM credentials_entity WHERE id = ?',
      [credentialId],
      (credentialError, existingCredential) => {
        database.close();
        if (credentialError) throw credentialError;

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

        if (!fs.existsSync(workflowMarker)) {
          runN8n(['import:workflow', '--input=/workflows/alerte_fraude.json']);
          runN8n(['publish:workflow', `--id=${workflowId}`]);
          fs.writeFileSync(workflowMarker, 'imported\n');
        }

        runN8n(['start']);
      },
    );
  },
);
