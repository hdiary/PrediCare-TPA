#!/bin/sh
# db-init entrypoint (P1): migrate, then load the dataset on FIRST start only.
#
#   1. wait for Postgres
#   2. alembic upgrade head              (idempotent)
#   3. if every file is already loaded -> stop here (restart = no work)
#   4. clean.py -> encrypt_identities.py -> load.py
#      Default load imports references only; invoices and prescriptions are
#      created from API submissions, never from historical dataset files.
#   5. delete the plaintext personal data
#
# Environment (see .env.example):
#   DATABASE_URL, IDENTITY_KEY            required
#   DATASET_DIR (default /data/dataset)   folder with the CSV files
#   LABELS_DIR  (optional)                folder with labels_*.csv
#   WORK_DIR    (default /work)           scratch space, wiped at the end
set -eu

DATASET_DIR="${DATASET_DIR:-/data/dataset}"
WORK_DIR="${WORK_DIR:-/work}"
APP_DIR="${APP_DIR:-/app}"
cd "$APP_DIR"

echo "[db-init] waiting for the database..."
python load.py --wait 90 --wait-only


# echo "[db-init] Checking if database exists..."
# psql -U $POSTGRES_USER -tc "SELECT 1 FROM pg_database WHERE datname = '$POSTGRES_DB'" | grep -q 1 || \
#     psql -U $POSTGRES_USER -c "CREATE DATABASE $POSTGRES_DB;"
    

echo "[db-init] applying migrations..."
alembic upgrade head

echo "[db-init] configuring the RAG agent database role..."
python configure_agent_role.py

if python load.py --is-initialised; then
# if python load.py --is-initialised --include-operational-data; then

    echo "[db-init] database already loaded, nothing to do."
    exit 0
fi

: "${IDENTITY_KEY:?IDENTITY_KEY is required to encrypt the identities}"
[ -d "$DATASET_DIR" ] || { echo "[db-init] ERROR: $DATASET_DIR not found"; exit 1; }

trap 'rm -rf "$WORK_DIR/secure"' EXIT   # never leave personal data behind
rm -rf "$WORK_DIR/clean" "$WORK_DIR/rejets" "$WORK_DIR/secure"
mkdir -p "$WORK_DIR"

echo "[db-init] cleaning..."
if [ -n "${LABELS_DIR:-}" ]; then
    python clean.py --src "$DATASET_DIR" --labels "$LABELS_DIR" \
        --out "$WORK_DIR/clean" --rejets "$WORK_DIR/rejets" \
        --secure "$WORK_DIR/secure"
else
    python clean.py --src "$DATASET_DIR" --out "$WORK_DIR/clean" \
        --rejets "$WORK_DIR/rejets" --secure "$WORK_DIR/secure"
fi

echo "[db-init] encrypting identities..."
python encrypt_identities.py --in "$WORK_DIR/secure/identites_pii.parquet" \
    --out "$WORK_DIR/secure/identites_chiffrees.parquet" --delete-source

echo "[db-init] loading..."
python load.py --clean-dir "$WORK_DIR/clean" --secure-dir "$WORK_DIR/secure"

echo "[db-init] done."
