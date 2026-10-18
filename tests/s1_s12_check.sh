#!/usr/bin/env bash
# Vérifications S1 et S12 sur la plateforme démarrée (preuves).
# Prérequis : DEMO_PASSWORD dans .env, comptes démo créés.
# ATTENTION : la partie S12 verrouille volontairement le compte pro@predicare.local pendant
# LOGIN_LOCKOUT_MINUTES (par défaut 15 min). Pour le déverrouiller tout de suite :
#   docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -c \
#   "UPDATE utilisateurs SET verrouille_jusqua=NULL, tentatives_echouees=0 WHERE email='pro@predicare.local';"
set -uo pipefail
cd "$(dirname "$0")/.."
set -a; [ -f .env ] && source .env; set +a
API=${API:-http://localhost:8000}
J='Content-Type: application/json'

login() { curl -s -X POST "$API/auth/login" -H "$J" \
  -d "{\"email\":\"$1\",\"password\":\"$2\"}"; }
token() { login "$1" "$DEMO_PASSWORD" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])'; }
code()  { curl -s -o /dev/null -w '%{http_code}' "$@"; }

echo "=== S1 : un assuré appelle les endpoints gestionnaire / admin (attendu : 403)"
T=$(token assure@predicare.local)
for path in "/alerts" "/admin/model" "/admin/ping"; do
  echo "GET $path -> $(code "$API$path" -H "Authorization: Bearer $T")"
done
echo "POST /alerts/FAC-00000001/decision -> $(code -X POST "$API/alerts/FAC-00000001/decision" \
  -H "Authorization: Bearer $T" -H "$J" -d '{"decision":"faux_positif"}')"
echo "GET /alerts sans jeton (attendu : 401) -> $(code "$API/alerts")"

echo
echo "=== S12 : mots de passe hachés (attendu : préfixe \$2b\$ = bcrypt, aucun mot de passe en clair)"
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT email, left(mot_de_passe_hash, 7) AS debut_hash, length(mot_de_passe_hash) AS longueur FROM utilisateurs;"

echo "=== S12 : durée de session (attendu : exp - iat = JWT_EXPIRE_MINUTES x 60 s)"
T=$(token gestionnaire@predicare.local)
python3 - "$T" <<'PY'
import base64, json, sys
payload = sys.argv[1].split(".")[1]
claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
print("durée de vie du jeton :", claims["exp"] - claims["iat"], "secondes")
PY

echo "=== S12 : échecs limités (attendu : 401 x N puis 429 même avec le bon mot de passe)"
for i in 1 2 3 4 5 6; do
  echo "tentative $i (mauvais mot de passe) -> $(code -X POST "$API/auth/login" -H "$J" \
    -d '{"email":"pro@predicare.local","password":"mauvais"}')"
done
echo "bon mot de passe après verrouillage (attendu 429) -> $(code -X POST "$API/auth/login" -H "$J" \
  -d "{\"email\":\"pro@predicare.local\",\"password\":\"$DEMO_PASSWORD\"}")"
