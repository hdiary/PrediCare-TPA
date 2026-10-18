#!/usr/bin/env bash
# backup.sh (P3-21) : sauvegarde chiffrée de la base PostgreSQL (+ volume MLflow si présent).
#
# Usage :  ./scripts/backup.sh
# Prérequis : fichier .env avec POSTGRES_USER, POSTGRES_DB et BACKUP_PASSPHRASE (>= 16 caractères).
# Sortie    : backups/predicare_AAAAMMJJ_HHMMSS.dump.enc (+ .sha256), AES-256 (openssl, PBKDF2).
# Rétention : BACKUP_RETENTION_DAYS (défaut 14) ; les sauvegardes plus anciennes sont supprimées.
# Quotidien : voir docs/guides/guide_exploitation.md (cron).
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] && { set -a; . ./.env; set +a; }
: "${POSTGRES_USER:?POSTGRES_USER manquant (.env)}"
: "${POSTGRES_DB:?POSTGRES_DB manquant (.env)}"
: "${BACKUP_PASSPHRASE:?BACKUP_PASSPHRASE manquant (.env) : openssl rand -base64 32}"
[ "${#BACKUP_PASSPHRASE}" -ge 16 ] || { echo "BACKUP_PASSPHRASE trop courte (16 caractères minimum)" >&2; exit 1; }

BACKUP_DIR="${BACKUP_DIR:-backups}"
RETENTION="${BACKUP_RETENTION_DAYS:-14}"
DB_SERVICE="${DB_SERVICE:-db}"
COMPOSE="${COMPOSE:-docker compose}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/predicare_${STAMP}.dump.enc"

umask 077
mkdir -p "$BACKUP_DIR"
TMP="$(mktemp "$BACKUP_DIR/.tmp.XXXXXX")"
trap 'rm -f "$TMP"' EXIT

# Le mot de passe de chiffrement passe par l'environnement du processus (jamais en argument visible).
export BACKUP_PASSPHRASE

echo "[backup] dump de $POSTGRES_DB ..."
$COMPOSE exec -T "$DB_SERVICE" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner \
  | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:BACKUP_PASSPHRASE > "$TMP"

# Un dump vide ou tronqué (échec de pg_dump) ne doit jamais être conservé comme sauvegarde valide.
SIZE="$(wc -c < "$TMP")"
if [ "$SIZE" -lt 200 ]; then
  echo "[backup] ÉCHEC : sauvegarde vide ou trop petite ($SIZE octets)" >&2
  exit 1
fi

mv "$TMP" "$OUT"
trap - EXIT
( cd "$BACKUP_DIR" && sha256sum "$(basename "$OUT")" > "$(basename "$OUT").sha256" )
echo "[backup] OK : $OUT ($SIZE octets)"

# Rétention
find "$BACKUP_DIR" -maxdepth 1 -name 'predicare_*.dump.enc*' -mtime +"$RETENTION" -print -delete \
  | sed 's/^/[backup] supprimé (ancien) : /' || true
