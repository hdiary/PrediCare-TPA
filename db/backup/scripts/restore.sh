#!/bin/sh
set -eu
umask 077

PGHOST="${PGHOST:-db}"
PGPORT="${PGPORT:-5432}"
PGDATABASE="${PGDATABASE:-predicare}"
PGUSER="${PGUSER:-postgres}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_DIR="${BACKUP_DIR%/}"
verify_only=false
target_db=
archive=

usage() {
    echo "Usage: restore.sh /backups/<backup>.dump.gpg [--target-db NAME] [--verify-only]" >&2
    exit 2
}

[ "$#" -gt 0 ] || usage
archive=$1
shift
while [ "$#" -gt 0 ]; do
    case "$1" in
        --target-db)
            [ "$#" -ge 2 ] || usage
            target_db=$2
            shift 2
            ;;
        --verify-only)
            verify_only=true
            shift
            ;;
        *)
            usage
            ;;
    esac
done

if [ -z "${BACKUP_ENCRYPTION_KEY:-}" ] || [ "${#BACKUP_ENCRYPTION_KEY}" -lt 32 ]; then
    echo "BACKUP_ENCRYPTION_KEY must contain at least 32 characters." >&2
    exit 2
fi
archive_name=${archive##*/}
[ "${archive%/*}" = "$BACKUP_DIR" ] || {
    echo "The backup must be a predicare_*.dump.gpg file in $BACKUP_DIR." >&2
    exit 2
}
case "$archive_name" in
    predicare_*.dump.gpg) ;;
    *)
        echo "The backup must be a predicare_*.dump.gpg file in $BACKUP_DIR." >&2
        exit 2
        ;;
esac
[ -f "$archive" ] || { echo "Backup file not found: $archive" >&2; exit 2; }

if [ "$verify_only" = true ]; then
    [ -z "$target_db" ] || {
        echo "--target-db cannot be combined with --verify-only." >&2
        exit 2
    }
    target_db="predicare_restore_check_$(date -u '+%Y%m%d%H%M%S')_$$"
elif [ -z "$target_db" ]; then
    echo "Specify --target-db to restore into a separate, new database." >&2
    exit 2
fi
case "$target_db" in
    ''|[!a-zA-Z_]*|*[!a-zA-Z0-9_]*)
        echo "Target database name must be a valid PostgreSQL identifier." >&2
        exit 2
        ;;
esac
if [ "$target_db" = "$PGDATABASE" ]; then
    echo "Refusing to restore over the source database '$PGDATABASE'." >&2
    exit 2
fi

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/predicare-restore.XXXXXX")
mkdir -m 0700 "$work_dir/gnupg"
created=false
restored=false
cleanup() {
    status=$?
    if [ "$created" = true ] && { [ "$restored" != true ] || [ "$verify_only" = true ]; }; then
        dropdb --if-exists --host="$PGHOST" --port="$PGPORT" \
            --username="$PGUSER" "$target_db" || \
            echo "WARNING: failed to remove temporary database '$target_db'." >&2
    fi
    rm -rf "$work_dir"
    exit "$status"
}
trap cleanup EXIT HUP INT TERM

key_file="$work_dir/passphrase"
dump_file="$work_dir/predicare.dump"
printf '%s' "$BACKUP_ENCRYPTION_KEY" > "$key_file"
chmod 0600 "$key_file"

echo "Decrypting and validating '$archive'."
gpg --homedir "$work_dir/gnupg" --batch --yes --pinentry-mode loopback \
    --passphrase-file "$key_file" --decrypt --output "$dump_file" "$archive"
pg_restore --list "$dump_file" > /dev/null

echo "Restoring into new database '$target_db' (source '$PGDATABASE' is unchanged)."
createdb --host="$PGHOST" --port="$PGPORT" --username="$PGUSER" \
    --template=template0 "$target_db"
created=true
pg_restore --exit-on-error --single-transaction \
    --host="$PGHOST" --port="$PGPORT" --username="$PGUSER" \
    --dbname="$target_db" "$dump_file"
restored=true

if [ "$verify_only" = true ]; then
    for table in factures predictions decisions_gestionnaires shap_explanations audit_log documents_vectorises; do
        source_count=$(psql --no-psqlrc --tuples-only --no-align \
            --host="$PGHOST" --port="$PGPORT" --username="$PGUSER" \
            --dbname="$PGDATABASE" --command="SELECT count(*) FROM public.\"$table\"")
        restored_count=$(psql --no-psqlrc --tuples-only --no-align \
            --host="$PGHOST" --port="$PGPORT" --username="$PGUSER" \
            --dbname="$target_db" --command="SELECT count(*) FROM public.\"$table\"")
        [ "$source_count" = "$restored_count" ] || {
            echo "Restore verification failed: $table has $source_count source rows and $restored_count restored rows." >&2
            exit 1
        }
        echo "Verified $table: $restored_count rows."
    done
    echo "Restore verification passed; the temporary database will be removed."
else
    echo "Restore complete. The new database '$target_db' is ready for validation."
fi
