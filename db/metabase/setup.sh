#!/bin/sh
set -e
MB="http://metabase:3000"
BI_DEFINITION_FILE="${BI_DEFINITION_FILE:-/dashboard.json}"
DASH_NAME=$(jq -r '.name' "$BI_DEFINITION_FILE")
BI_VERSION=$(jq -r '.version' "$BI_DEFINITION_FILE")
DASH_DESCRIPTION="PrediCare BI definition v$BI_VERSION"

# ---------- helpers ----------
api() {  # usage: api METHOD /path [curl args...]
  m=$1; p=$2; shift 2
  out=$(curl -s -w '\n%{http_code}' -X "$m" "$MB/api$p" \
    -H "Content-Type: application/json" -H "X-Metabase-Session: $SESSION" "$@")
  code=$(printf '%s' "$out" | tail -n1)
  body=$(printf '%s' "$out" | sed '$d')
  case "$code" in
    2*) printf '%s' "$body" ;;
    *)  echo "ERREUR HTTP $code sur $m $p : $body" >&2; return 1 ;;
  esac
}

add_card() {  # $1 name, $2 display, $3 SQL
  body=$(jq -n --arg name "$1" --arg disp "$2" --arg sql "$3" --argjson db "$DB_ID" '{
    name:$name, display:$disp, visualization_settings:{},
    dataset_query:{type:"native", database:$db, native:{query:$sql, "template-tags":{
      date_debut:{id:"t1", name:"date_debut", "display-name":"Date début", type:"date"},
      date_fin:{id:"t2", name:"date_fin", "display-name":"Date fin", type:"date"}}}}}')
  api POST /card -d "$body" | jq -r '.id // empty'
}

# ---------- 1. wait for Metabase ----------
until curl -sf "$MB/api/health" | grep -q ok; do
  echo "En attente de Metabase..."; sleep 5
done

# ---------- 2. first-time setup (admin account) ----------
TOKEN=$(curl -s "$MB/api/session/properties" | jq -r '.["setup-token"]')
if [ "$TOKEN" != "null" ] && [ -n "$TOKEN" ]; then
  curl -sf -X POST "$MB/api/setup" -H "Content-Type: application/json" -d "$(jq -n \
    --arg t "$TOKEN" --arg e "$MB_ADMIN_EMAIL" --arg p "$MB_ADMIN_PASSWORD" \
    --arg db "$POSTGRES_DB" --arg rp "$METABASE_RO_PASSWORD" '{
      token:$t,
      user:{first_name:"Admin", last_name:"PrediCare", email:$e, password:$p},
      prefs:{site_name:"PrediCare TPA", site_locale:"fr", allow_tracking:false},
      database:{engine:"postgres", name:"PrediCare", details:{
        host:"db", port:5432, dbname:$db, user:"metabase_ro", password:$rp, ssl:false}}
    }')" > /dev/null
  echo "Metabase configuré."
fi

# ---------- 3. API login ----------
SESSION=$(curl -sf -X POST "$MB/api/session" -H "Content-Type: application/json" \
  -d "$(jq -n --arg u "$MB_ADMIN_EMAIL" --arg p "$MB_ADMIN_PASSWORD" '{username:$u,password:$p}')" \
  | jq -r .id)
[ -n "$SESSION" ] && [ "$SESSION" != "null" ] || { echo "ERREUR : connexion admin impossible (vérifier MB_ADMIN_EMAIL / MB_ADMIN_PASSWORD)." >&2; exit 1; }

# ---------- 4. idempotence: skip only if the dashboard already has cards ----------
DASH_OLD=$(api GET /dashboard | jq -r --arg n "$DASH_NAME" \
  '[.[] | select(.name==$n and (.archived|not))][0].id // empty')
if [ -n "$DASH_OLD" ]; then
  DASH_INFO=$(api GET "/dashboard/$DASH_OLD")
  NB=$(printf '%s' "$DASH_INFO" | jq '(.dashcards // .ordered_cards // []) | length')
  DESCRIPTION=$(printf '%s' "$DASH_INFO" | jq -r '.description // ""')
  if [ "$NB" -gt 0 ] && [ "$DESCRIPTION" = "$DASH_DESCRIPTION" ]; then
    echo "Dashboard déjà à jour ($NB cartes, version $BI_VERSION)."
    exit 0
  fi
  echo "Dashboard existant obsolète ou vide : archivage avant recréation."
  api PUT "/dashboard/$DASH_OLD" -d '{"archived":true}' > /dev/null
fi

# ---------- 5. database id (find, add or repair the connection) ----------
DB_PAYLOAD=$(jq -n --arg db "$POSTGRES_DB" --arg rp "$METABASE_RO_PASSWORD" '{
  engine:"postgres", name:"PrediCare",
  details:{host:"db", port:5432, dbname:$db, user:"metabase_ro", password:$rp, ssl:false}}')

DB_ID=$(api GET /database | jq -r \
  '(.data // .) | map(select(.engine=="postgres" and (.is_sample|not))) | .[0].id // empty')
if [ -z "$DB_ID" ]; then
  echo "Base absente de Metabase : ajout via l'API."
  DB_ID=$(api POST /database -d "$DB_PAYLOAD" | jq -r '.id // empty')
else
  api PUT "/database/$DB_ID" -d "$DB_PAYLOAD" > /dev/null
fi
[ -n "$DB_ID" ] || { echo "ERREUR : impossible d'obtenir l'ID de la base." >&2; exit 1; }
api POST "/database/$DB_ID/sync_schema" > /dev/null
echo "Base PrediCare : ID $DB_ID"

# ---------- 6. archive cards from older dashboard definitions ----------
CARD_NAMES=$(jq -c '[.cards[].name] + [
  "Factures traitées", "Montant économisé",
  "Taux de détection (Recall, %)",
  "Taux de confirmation des alertes (%)", "Volumes par mois",
  "Montant total vs alerté", "Top 10 prestataires alertés"]' \
  "$BI_DEFINITION_FILE")
for CID in $(api GET /card | jq -r --argjson names "$CARD_NAMES" \
  '.[] | select((.archived|not) and (.name as $n | $names | index($n))) | .id'); do
  api PUT "/card/$CID" -d '{"archived":true}' > /dev/null
done

# ---------- 7. cards from the versioned, portable BI definition ----------
CARD_IDS='{}'
while IFS= read -r CARD; do
  KEY=$(printf '%s' "$CARD" | jq -r '.key')
  NAME=$(printf '%s' "$CARD" | jq -r '.name')
  DISPLAY=$(printf '%s' "$CARD" | jq -r '.display')
  SQL=$(printf '%s' "$CARD" | jq -r '.sql')
  CARD_ID=$(add_card "$NAME" "$DISPLAY" "$SQL")
  [ -n "$CARD_ID" ] || { echo "ERREUR : carte '$NAME' non créée." >&2; exit 1; }
  CARD_IDS=$(printf '%s' "$CARD_IDS" | jq --arg key "$KEY" --argjson id "$CARD_ID" \
    '. + {($key): $id}')
done <<EOF
$(jq -c '.cards[]' "$BI_DEFINITION_FILE")
EOF

# ---------- 8. dashboard + layout + date filters ----------
DASH_ID=$(api POST /dashboard -d "$(jq -n --arg n "$DASH_NAME" \
  --arg d "$DASH_DESCRIPTION" '{name:$n, description:$d}')" | jq -r '.id // empty')
[ -n "$DASH_ID" ] || { echo "ERREUR : dashboard non créé." >&2; exit 1; }

LAYOUT=$(jq -n --argjson cards "$CARD_IDS" --slurpfile definition "$BI_DEFINITION_FILE" '
  def mappings(c):
    $definition[0].filters | map({
      parameter_id: .id,
      card_id: c,
      target: ["variable", ["template-tag", .slug]]
    });
  {
    parameters: $definition[0].filters,
    dashcards: [
      $definition[0].cards | to_entries[] |
      .key as $index | .value as $card |
      ($cards[$card.key]) as $card_id |
      {
        id: -(($index | tonumber) + 1),
        card_id: $card_id,
        row: $card.layout.row,
        col: $card.layout.col,
        size_x: $card.layout.width,
        size_y: $card.layout.height,
        parameter_mappings: mappings($card_id),
        visualization_settings: {}
      }
    ]
  }')
api PUT "/dashboard/$DASH_ID" -d "$LAYOUT" > /dev/null

# ---------- 10. signed embedding (non-blocking) ----------
api PUT "/dashboard/$DASH_ID" -d '{
  "enable_embedding": true,
  "embedding_params": {"date_debut":"enabled","date_fin":"enabled"}}' > /dev/null \
  || echo "AVERTISSEMENT : embedding non activé (à traiter lors de l'intégration au front)." >&2

echo "Dashboard créé. ID = $DASH_ID"