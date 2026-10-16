#!/bin/sh
set -e
MB="http://metabase:3000"
DASH_NAME="PrediCare : Pilotage"

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
  NB=$(api GET "/dashboard/$DASH_OLD" | jq '(.dashcards // .ordered_cards // []) | length')
  if [ "$NB" -gt 0 ]; then echo "Dashboard déjà présent ($NB cartes)."; exit 0; fi
  echo "Dashboard vide détecté : nettoyage et recréation."
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

# ---------- 6. archive orphan cards with the same names ----------
for NAME in "Factures traitées" "Montant économisé" "Taux de détection (Recall, %)" \
            "Taux de confirmation des alertes (%)" "Volumes par mois" \
            "Montant total vs alerté" "Top 10 prestataires alertés"; do
  for CID in $(api GET /card | jq -r --arg n "$NAME" '.[] | select(.name==$n and (.archived|not)) | .id'); do
    api PUT "/card/$CID" -d '{"archived":true}' > /dev/null
  done
done

# ---------- 7. SQL (reads only the view v_bi_factures) ----------
SQL_NB=$(cat <<'EOF'
SELECT COUNT(*) AS factures_traitees
FROM v_bi_factures v WHERE 1=1
[[AND v.date_facture >= {{date_debut}}]] [[AND v.date_facture <= {{date_fin}}]]
EOF
)
SQL_RECALL=$(cat <<'EOF'
SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE v.is_alert)
       / NULLIF(COUNT(*), 0), 1) AS taux_detection_pct
FROM v_bi_factures v
WHERE v.est_fraude AND v.est_valide
[[AND v.date_facture >= {{date_debut}}]] [[AND v.date_facture <= {{date_fin}}]]
EOF
)
SQL_CONF=$(cat <<'EOF'
SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE v.decision = 'rejete')
       / NULLIF(COUNT(*), 0), 1) AS taux_confirmation_pct
FROM v_bi_factures v
WHERE v.is_alert AND v.decision IN ('valide', 'rejete')
[[AND v.date_facture >= {{date_debut}}]] [[AND v.date_facture <= {{date_fin}}]]
EOF
)
SQL_ECO=$(cat <<'EOF'
SELECT COALESCE(SUM(v.montant_total), 0) AS montant_economise
FROM v_bi_factures v
WHERE v.is_alert AND v.decision = 'rejete'
[[AND v.date_facture >= {{date_debut}}]] [[AND v.date_facture <= {{date_fin}}]]
EOF
)
SQL_VOL=$(cat <<'EOF'
SELECT date_trunc('month', v.date_facture) AS mois, COUNT(*) AS nb_factures
FROM v_bi_factures v WHERE 1=1
[[AND v.date_facture >= {{date_debut}}]] [[AND v.date_facture <= {{date_fin}}]]
GROUP BY 1 ORDER BY 1
EOF
)
SQL_ALERTE=$(cat <<'EOF'
SELECT date_trunc('month', v.date_facture) AS mois,
       SUM(v.montant_total) AS montant_total,
       SUM(v.montant_total) FILTER (WHERE v.is_alert) AS montant_alerte
FROM v_bi_factures v WHERE 1=1
[[AND v.date_facture >= {{date_debut}}]] [[AND v.date_facture <= {{date_fin}}]]
GROUP BY 1 ORDER BY 1
EOF
)
SQL_PRESTA=$(cat <<'EOF'
SELECT v.prestataire_nom, COUNT(*) AS nb_alertes
FROM v_bi_factures v
WHERE v.is_alert
[[AND v.date_facture >= {{date_debut}}]] [[AND v.date_facture <= {{date_fin}}]]
GROUP BY 1 ORDER BY 2 DESC LIMIT 10
EOF
)

# ---------- 8. cards ----------
C1=$(add_card "Factures traitées"                    scalar "$SQL_NB")
C2=$(add_card "Montant économisé"                    scalar "$SQL_ECO")
C3=$(add_card "Taux de détection (Recall, %)"        scalar "$SQL_RECALL")
C4=$(add_card "Taux de confirmation des alertes (%)" scalar "$SQL_CONF")
C5=$(add_card "Volumes par mois"                     line   "$SQL_VOL")
C6=$(add_card "Montant total vs alerté"              bar    "$SQL_ALERTE")
C7=$(add_card "Top 10 prestataires alertés"          bar    "$SQL_PRESTA")

for v in "$C1" "$C2" "$C3" "$C4" "$C5" "$C6" "$C7"; do
  [ -n "$v" ] || { echo "ERREUR : une carte n'a pas été créée (voir messages ci-dessus)." >&2; exit 1; }
done

# ---------- 9. dashboard + layout + filters ----------
DASH_ID=$(api POST /dashboard -d "$(jq -n --arg n "$DASH_NAME" '{name:$n}')" | jq -r '.id // empty')
[ -n "$DASH_ID" ] || { echo "ERREUR : dashboard non créé." >&2; exit 1; }

LAYOUT=$(jq -n \
  --argjson c1 "$C1" --argjson c2 "$C2" --argjson c3 "$C3" --argjson c4 "$C4" \
  --argjson c5 "$C5" --argjson c6 "$C6" --argjson c7 "$C7" '
  def m(c): [
    {parameter_id:"date_debut", card_id:c, target:["variable",["template-tag","date_debut"]]},
    {parameter_id:"date_fin",   card_id:c, target:["variable",["template-tag","date_fin"]]}];
  def dc(i; c; r; col; w; h): {id:i, card_id:c, row:r, col:col, size_x:w, size_y:h,
                               parameter_mappings:m(c), visualization_settings:{}};
  { parameters: [
      {id:"date_debut", name:"Date début", slug:"date_debut", type:"date/single"},
      {id:"date_fin",   name:"Date fin",   slug:"date_fin",   type:"date/single"}],
    dashcards: [
      dc(-1;$c1;0;0;6;3),  dc(-2;$c2;0;6;6;3), dc(-3;$c3;0;12;6;3), dc(-4;$c4;0;18;6;3),
      dc(-5;$c5;3;0;12;7), dc(-6;$c6;3;12;12;7),
      dc(-7;$c7;10;0;24;7)] }')
api PUT "/dashboard/$DASH_ID" -d "$LAYOUT" > /dev/null

# ---------- 10. signed embedding (non-blocking) ----------
api PUT "/dashboard/$DASH_ID" -d '{
  "enable_embedding": true,
  "embedding_params": {"date_debut":"enabled","date_fin":"enabled"}}' > /dev/null \
  || echo "AVERTISSEMENT : embedding non activé (à traiter lors de l'intégration au front)." >&2

echo "Dashboard créé. ID = $DASH_ID"