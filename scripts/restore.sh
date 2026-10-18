#!/usr/bin/env bash
# restore.sh (P3-21 / test S9) : restaure une sauvegarde chiffrée.
#
# Usage :
#   ./scripts/restore.sh --verify backups/predicare_XXXX.dump.enc
#       Restaure dans une base TEMPORAIRE, affiche le nombre de lignes des tables clés, puis la
#       supprime. Ne touche PAS à la base de production : c'est le mode « test de restauration ».
#   ./scripts/restore.sh --yes backups/predicare_XXXX.dump.enc
#       Restaure sur la base de production (écrase les données actuelles). Demande une
#       confirmation tapée, sauf avec --yes. Arrêter l'API avant : docker compose stop api
set -euo pipefail
cd "$(dirname "$0")/.."

MODE="prod"; ASSUME_YES="no"
while [ $# -gt 1 ]; do
  case "$1" in
    --verify) MODE="verify" ;;
    --yes)    ASSUME_YES="yes" ;;
    *) echo "Option inconnue : $1" >&2; exit 2 ;;
  esac; shift
done
FILE="${1:-}"
[ -n "$FILE" ] && [ -f "$FILE" ] || { echo "Usage : restore.sh [--verify|--yes] <fichier .dump.enc>" >&2; exit 2; }

[ -f .env ] && { set -a; . ./.env; set +a; }
: "${POSTGRES_USER:?POSTGRES_USER manquant (.env)}"
: "${POSTGRES_DB:?POSTGRES_DB manquant (.env)}"
: "${BACKUP_PASSPHRASE:?BACKUP_PASSPHRASE manquant (.env)}"
export BACKUP_PASSPHRASE
DB_SERVICE="${DB_SERVICE:-db}"
COMPOSE="${COMPOSE:-docker compose}"
KEY_TABLES="${KEY_TABLES:-utilisateurs factures predictions decisions_gestionnaire journal_audit configuration}"

# 1. Intégrité : somme de contrôle si elle existe
if [ -f "$FILE.sha256" ]; then
  ( cd "$(dirname "$FILE")" && sha256sum -c "$(basename "$FILE").sha256" ) \
    || { echo "[restore] ÉCHEC : somme de contrôle invalide (fichier corrompu)" >&2; exit 1; }
fi

psql_db() { $COMPOSE exec -T "$DB_SERVICE" psql -U "$POSTGRES_USER" -d "$1" -v ON_ERROR_STOP=1 -qtAX "${@:2}"; }

if [ "$MODE" = "verify" ]; then
  TARGET="predicare_restore_test"
  echo "[restore] mode vérification : base temporaire $TARGET"
  psql_db postgres -c "DROP DATABASE IF EXISTS $TARGET" >/dev/null
  psql_db postgres -c "CREATE DATABASE $TARGET" >/dev/null
  cleanup_verify() { psql_db postgres -c "DROP DATABASE IF EXISTS $TARGET" >/dev/null || true; }
  trap cleanup_verify EXIT
else
  TARGET="$POSTGRES_DB"
  if [ "$ASSUME_YES" != "yes" ]; then
    echo "ATTENTION : cette opération ÉCRASE la base '$TARGET'."
    read -r -p "Tapez le nom de la base pour confirmer : " ANSWER
    [ "$ANSWER" = "$TARGET" ] || { echo "Annulé."; exit 1; }
  fi
fi

# 2. Déchiffrement puis restauration (un mauvais mot de passe fait échouer openssl : set -o pipefail)
echo "[restore] déchiffrement et restauration dans $TARGET ..."
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:BACKUP_PASSPHRASE -in "$FILE" \
  | $COMPOSE exec -T "$DB_SERVICE" pg_restore -U "$POSTGRES_USER" -d "$TARGET" \
      --clean --if-exists --no-owner --exit-on-error

# 3. Contrôle : nombre de lignes des tables clés
echo "[restore] contrôle des tables clés :"
FAIL=0
for T in $KEY_TABLES; do
  N="$(psql_db "$TARGET" -c "SELECT count(*) FROM $T" 2>/dev/null || echo "ABSENTE")"
  printf '  %-26s %s\n' "$T" "$N"
  [ "$N" = "ABSENTE" ] && FAIL=1
done
[ "$FAIL" -eq 0 ] || { echo "[restore] ÉCHEC : table(s) manquante(s)" >&2; exit 1; }
echo "[restore] OK ($MODE)"
