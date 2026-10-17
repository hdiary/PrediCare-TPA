#!/bin/sh
set -eu
umask 077

PGHOST="${PGHOST:-db}"
PGPORT="${PGPORT:-5432}"
PGDATABASE="${PGDATABASE:-predicare}"
PGUSER="${PGUSER:-postgres}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

if [ -z "${BACKUP_ENCRYPTION_KEY:-}" ] || [ "${#BACKUP_ENCRYPTION_KEY}" -lt 32 ]; then
    echo "BACKUP_ENCRYPTION_KEY must contain at least 32 characters." >&2
    exit 2
fi
case "$BACKUP_RETENTION_DAYS" in
    ''|*[!0-9]*)
        echo "BACKUP_RETENTION_DAYS must be a positive integer." >&2
        exit 2
        ;;
esac
if [ "$BACKUP_RETENTION_DAYS" -lt 1 ]; then
    echo "BACKUP_RETENTION_DAYS must be at least 1." >&2
    exit 2
fi

mkdir -p "$BACKUP_DIR"
work_dir=$(mktemp -d "${TMPDIR:-/tmp}/predicare-backup.XXXXXX")
encrypted_tmp=
cleanup() {
    rm -rf "$work_dir"
    if [ -n "$encrypted_tmp" ]; then
        rm -f "$encrypted_tmp"
    fi
}
trap cleanup EXIT HUP INT TERM

key_file="$work_dir/passphrase"
dump_file="$work_dir/predicare.dump"
verified_file="$work_dir/verified.dump"
printf '%s' "$BACKUP_ENCRYPTION_KEY" > "$key_file"
chmod 0600 "$key_file"

timestamp=$(date -u '+%Y%m%dT%H%M%SZ')
backup_file="$BACKUP_DIR/predicare_${timestamp}.dump.gpg"
encrypted_tmp=$(mktemp "$BACKUP_DIR/.predicare_${timestamp}.XXXXXX")

echo "Creating PostgreSQL custom-format backup for '$PGDATABASE'."
mkdir -m 0700 "$work_dir/gnupg"

pg_dump --format=custom \
    --host="$PGHOST" --port="$PGPORT" --username="$PGUSER" \
    --dbname="$PGDATABASE" --file="$dump_file"
pg_restore --list "$dump_file" > /dev/null

gpg --homedir "$work_dir/gnupg" --batch --yes --pinentry-mode loopback \
    --passphrase-file "$key_file" --symmetric --cipher-algo AES256 \
    --s2k-digest-algo SHA256 --output "$encrypted_tmp" "$dump_file"
chmod 0600 "$encrypted_tmp"

gpg --homedir "$work_dir/gnupg" --batch --yes --pinentry-mode loopback \
    --passphrase-file "$key_file" --decrypt --output "$verified_file" \
    "$encrypted_tmp"
cmp -s "$dump_file" "$verified_file"
pg_restore --list "$verified_file" > /dev/null

mv "$encrypted_tmp" "$backup_file"
encrypted_tmp=
echo "Verified encrypted backup: $backup_file"

find "$BACKUP_DIR" -maxdepth 1 -type f -name 'predicare_*.dump.gpg' \
    -mtime "+$BACKUP_RETENTION_DAYS" -delete
