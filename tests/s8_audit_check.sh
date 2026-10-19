#!/usr/bin/env bash
# Test S8 (AI Act art. 12) : une prédiction + une décision laissent des lignes d'audit.
# Prérequis : plateforme démarrée, tests/sample_invoice.json rempli avec des identifiants réels,
# DEMO_PASSWORD présent dans .env. Changer facture_id à chaque exécution.
# NB : la décision n'est possible que si la facture a déclenché une alerte (score >= seuil).
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [ -f .env ] && source .env; set +a
API=${API:-http://localhost:8000}

TOKEN=$(curl -sf -X POST "$API/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"gestionnaire@predicare.local\",\"password\":\"$DEMO_PASSWORD\"}" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

echo "--- /predict"
RESP=$(curl -s -X POST "$API/predict" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d @tests/sample_invoice.json)
echo "$RESP"
FID=$(python3 -c 'import json; print(json.load(open("tests/sample_invoice.json"))["facture_id"])')

echo "--- décision sur la facture $FID"
curl -s -X POST "$API/alerts/$FID/decision" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"decision":"a_investiguer","commentaire":"test S8"}'
echo

echo "--- lignes d'audit"
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
 "SELECT horodatage, type_evenement, entite_id, version_modele,
         entree IS NOT NULL AS a_entree, sortie IS NOT NULL AS a_sortie
  FROM journal_audit WHERE entite_id = '$FID' ORDER BY audit_id;"
