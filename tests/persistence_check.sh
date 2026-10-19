#!/usr/bin/env bash
# persistence_check.sh (P3-22) : les données survivent-elles à un redémarrage des conteneurs ?
#
# Principe : compte les lignes des tables clés, modifie le seuil d'alerte (donnée + audit),
# fait `docker compose down` (SANS -v : les volumes sont conservés) puis `up -d`,
# et vérifie que tout est identique. Restaure ensuite le seuil d'origine.
#
# Usage : ./tests/persistence_check.sh      (API sur http://localhost:8000 par défaut)
# Prérequis : .env avec POSTGRES_USER, POSTGRES_DB, DEMO_PASSWORD ; compte admin@predicare.local.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && { set -a; . ./.env; set +a; }
API="${API:-http://localhost:8000}"
COMPOSE="${COMPOSE:-docker compose}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@predicare.local}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-${DEMO_PASSWORD:?DEMO_PASSWORD ou ADMIN_PASSWORD requis}}"
TABLES="utilisateurs factures predictions decisions_gestionnaire journal_audit alertes_prescription"
MARKER="0.7777"

jget() { python3 -c "import sys,json; print(json.load(sys.stdin)$1)"; }
login() {
  curl -fsS -X POST "$API/auth/login" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" | jget "['access_token']"
}
sql() { $COMPOSE exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -qtAX -c "$1"; }
snapshot() {
  for t in $TABLES; do printf '%s=%s\n' "$t" "$(sql "SELECT count(*) FROM $t" 2>/dev/null || echo ABSENTE)"; done
  printf 'seuil=%s\n' "$(sql "SELECT valeur FROM configuration WHERE cle='seuil_alerte'")"
}
wait_health() {
  for _ in $(seq 1 60); do
    curl -fsS "$API/health" >/dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}

echo "[1/6] connexion admin"
TOKEN="$(login)"
ORIGINAL="$(curl -fsS "$API/admin/threshold" -H "Authorization: Bearer $TOKEN" | jget "['seuil']")"

echo "[2/6] modification du seuil ($ORIGINAL -> $MARKER)"
curl -fsS -X PUT "$API/admin/threshold" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d "{\"seuil\": $MARKER}" >/dev/null

echo "[3/6] état avant redémarrage"
snapshot | tee /tmp/persist_before.txt

echo "[4/6] docker compose down (volumes conservés) puis up -d"
$COMPOSE down
$COMPOSE up -d
wait_health || { echo "ÉCHEC : l'API ne répond pas après redémarrage"; exit 1; }

echo "[5/6] état après redémarrage"
snapshot | tee /tmp/persist_after.txt

echo "[6/6] comparaison, connexion et restauration du seuil"
STATUS=0
diff /tmp/persist_before.txt /tmp/persist_after.txt && echo "  données identiques" || STATUS=1
TOKEN="$(login)" && echo "  connexion possible après redémarrage" || STATUS=1
curl -fsS -X PUT "$API/admin/threshold" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d "{\"seuil\": $ORIGINAL}" >/dev/null
[ "$STATUS" -eq 0 ] && echo "PERSISTANCE : OK" || echo "PERSISTANCE : ÉCHEC"
exit "$STATUS"
