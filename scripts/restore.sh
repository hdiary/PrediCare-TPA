#!/bin/sh
set -eu

if [ "$#" -lt 1 ]; then
    echo "Usage: restore.sh <backup-file-name> [--target-db NAME] [--verify-only]" >&2
    exit 2
fi

archive_name=${1##*/}
case "$archive_name" in
    predicare_*.dump.gpg) ;;
    *)
        echo "Provide the name of a predicare_*.dump.gpg file in ./backups." >&2
        exit 2
        ;;
esac
shift

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

exec docker compose --profile backup run --rm --build -T \
    -e "BACKUP_DIR=${BACKUP_DIR:-/backups}" db-backup \
    restore.sh "${BACKUP_DIR:-/backups}/$archive_name" "$@"
