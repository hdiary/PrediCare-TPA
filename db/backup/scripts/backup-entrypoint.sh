#!/bin/sh
set -eu

command=${1:-schedule-backup.sh}
if [ "$#" -gt 0 ]; then
    shift
fi

case "$command" in
    backup.sh|restore.sh|schedule-backup.sh)
        exec "/usr/local/bin/predicare/$command" "$@"
        ;;
    *)
        echo "Unknown backup command: $command" >&2
        exit 2
        ;;
esac
