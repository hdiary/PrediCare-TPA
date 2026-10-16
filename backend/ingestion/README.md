# PrediCare-TPA - Readme backend/ingestion


# PrediCare TPA — `backend/ingestion` (P1 : données & base)

Ce dossier transforme le jeu de données brut en base PostgreSQL propre, pseudonymisée,
avec les identités chiffrées. Il est la **source unique** des données pour P2 (ML),
P3 (API), P4 (RAG / agent).

```
dataset/ (CSV bruts)
   │  clean.py            nettoyage + rejets + pseudonymes déjà présents vérifiés
   ▼
data/clean/*.parquet   data/secure/identites_pii.parquet   data/rejets/*.csv
   │                          │ encrypt_identities.py (Fernet)
   │                          ▼
   │                   data/secure/identites_chiffrees.parquet
   ▼                          ▼
   └──────────► load.py (Alembic + COPY/upsert) ──► PostgreSQL 16 + pgvector
```

## 1. Contenu

| Fichier / dossier                | Rôle                                                                                                           |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `clean.py`                     | Nettoyage par table, rejets motivés (`data/rejets/`), `_manifest.json`, code de sortie 2 si > 5 % rejetés |
| `pseudo.py`                    | Fonction de pseudonymisation figée (HMAC-SHA256 →`ASS-` + 10 hex). Ne jamais la modifier                    |
| `encrypt_identities.py`        | Chiffre les 7 champs d'identité (Fernet), versionnage de clé                                                  |
| `migrations/`, `alembic.ini` | Schéma versionné (extensions, tables métier, identités + rôles,`ingestion_log`, vues)                    |
| `load.py`                      | Charge les Parquet en base, idempotent (SHA-256 + upsert)                                                       |
| `db_init/`                     | Service Docker`db-init` : migrations + chargement automatique au premier démarrage                           |
| `docker-compose*.yml`          | Postgres +`db-init`                                                                                           |
| `test_*.py`                    | Tests (`pytest`)                                                                                              |
| `.env.example`                 | Modèle de configuration (copier en`.env`)                                                                    |

## 2. Qui crée la base ?

| Situation                      | Création de la base`predicare`                                                                                                                                                              |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Docker (recommandé)** | **Automatique** : l'image Postgres crée la base depuis `POSTGRES_DB` au premier démarrage du volume. Puis `db-init` lance les migrations et `load.py`. Rien à faire à la main. |
| Postgres installé en local    | **Manuelle, une seule fois** : `createdb predicare`. `load.py` ne crée jamais la base elle-même, il crée seulement les tables (via Alembic), rôles et vues.                      |

Les extensions (`vector`, etc.) sont créées par la migration 0001 : elles demandent un
super-utilisateur (c'est le cas de l'utilisateur Postgres du conteneur) et l'image
`pgvector/pgvector:pg16`. Un Postgres local sans pgvector échouera à cette étape.

## 3. Prérequis

- Docker + Docker Compose v2, **ou** Python 3.11+ et PostgreSQL 16 avec pgvector
- Le dataset (CSV) placé dans `backend/ingestion/dataset/` (**jamais dans Git**)

## 4. Démarrage rapide (Docker)

Depuis `backend/ingestion/` :

```bash
cp .env.example .env
python encrypt_identities.py --gen-key        # copier la clé dans IDENTITY_KEY (.env)
# renseigner aussi PSEUDO_KEY et les mots de passe de la base (voir .env.example)

pip install -r db_init/requirements.txt pytest
python clean.py                               # -> data/clean, data/secure, data/rejets
python encrypt_identities.py --delete-source  # chiffre, vérifie, supprime le fichier en clair

docker compose -f docker-compose.db.yml up -d # base + migrations + chargement
```

Premier démarrage : `db-init` applique les migrations puis charge les données.
Redémarrages suivants : il détecte que la base est initialisée et ne recharge rien
(idempotence). Pour forcer un rechargement : `python load.py --force`.

> `pseudo.py` n'est **pas** exécuté par `db-init` : les `assure_id` du dataset sont déjà
> des pseudonymes. `pseudo.py` sert pour tout *nouvel* assuré et aux tests.

## 5. Exécution manuelle (sans Docker)

```bash
export DATABASE_URL=postgresql+psycopg://user:motdepasse@localhost:5432/predicare
alembic upgrade head
python load.py                 # ou --skip-identities si IDENTITY_KEY absente
```

## 6. Contrôle qualité et tests

```bash
python quality_check.py --mode raw   --src dataset      # avant nettoyage
python quality_check.py --mode clean                    # après clean.py
pytest -v                                               # pseudo, chiffrement, chargement
export PREDICARE_TEST_DATABASE_URL=... PREDICARE_DATASET=dataset   # active test_load.py
```

## 7. Règles de sécurité (obligatoires pour toute l'équipe)

1. **Jamais dans Git** : `.env`, `data/`, `dataset/`, `labels/`. Vérifier :
   `git check-ignore -v data/secure/identites_pii.parquet` doit afficher une règle.
2. Le fichier `identites_pii.parquet` (en clair) est supprimé dès le chiffrement (`--delete-source`).
3. `PSEUDO_KEY` et `IDENTITY_KEY` : chacun dans son `.env`, partagés hors Git (gestionnaire de mots de passe). Perdre `IDENTITY_KEY` = identités illisibles.
4. Rôles Postgres (moindre privilège) :

| Rôle               | Qui l'utilise                                                       | Accès                                               |
| ------------------- | ------------------------------------------------------------------- | ---------------------------------------------------- |
| `app_rw`          | P2, P3, P4 (services applicatifs)                                   | tables métier,**aucun accès** aux identités |
| `identity_reader` | P3 uniquement (affichage d'une alerte à un gestionnaire habilité) | uniquement`identites_chiffrees`                    |
| `agent_ro`        | agent P4                                                            | lecture seule sur les vues prévues (J3)             |

5. Pour le modèle (P2) : utiliser les vues `v_*_features`. Les colonnes de fuite
   (`montant_pris_en_charge`, `reste_a_charge`, `statut`, `motif_rejet`, `date_traitement`)
   en sont exclues.
6. Coordonnées des prestataires (`nom`, `adresse`, `telephone`, `numero_onm`, `nif`) : en clair
   (données professionnelles), mais **jamais** features du modèle ni sorties d'API/agent.

## 8. Dépannage

| Symptôme                               | Cause / remède                                                             |
| --------------------------------------- | --------------------------------------------------------------------------- |
| `clean.py` sort avec le code 2        | > 5 % de lignes rejetées : lire`data/rejets/*.csv` et `_manifest.json` |
| `IDENTITY_KEY is not set`             | clé absente du`.env`                                                     |
| `load.py` : code 3 ou 4               | base injoignable / non initialisée (voir le message,`--wait 60`)         |
| `extension "vector" is not available` | image Postgres sans pgvector : utiliser`pgvector/pgvector:pg16`           |
| `[FAIL] data/secure/ ignored by Git`  | ajouter`data/` au `.gitignore` racine<br />                             |


## 9. unification avec docker

Un seul docker-compose.yml à la racine pour toute l’équipe. Fais-lui inclure celui de P1, sans le recopier :
yaml
   include:
     - backend/ingestion/docker-compose.db.yml
