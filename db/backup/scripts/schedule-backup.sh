#!/bin/sh
set -eu

interval="${BACKUP_INTERVAL_SECONDS:-86400}"
case "$interval" in
    ''|*[!0-9]*)
        echo "BACKUP_INTERVAL_SECONDS must be a positive integer." >&2
        exit 2
        ;;
esac
if [ "$interval" -lt 60 ]; then
    echo "BACKUP_INTERVAL_SECONDS must be at least 60." >&2
    exit 2
fi

while :; do
    if /usr/local/bin/predicare/backup.sh; then
        sleep "$interval"
    else
        echo "Backup failed; retrying in one hour." >&2
        sleep 3600
    fi
done
