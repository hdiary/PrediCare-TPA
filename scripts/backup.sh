#!/bin/sh
set -eu
# db-backup mounts and archives the models_data Docker volume with PostgreSQL.

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

exec docker compose --profile backup run --rm --build -T \
    -e "BACKUP_DIR=${BACKUP_DIR:-/backups}" db-backup backup.sh "$@"
