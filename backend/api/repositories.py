"""Accès SQL (tables du contrat de données v0.1).

Seul endroit qui connaît les noms de tables et de colonnes métier.
"""
from datetime import date, time

import psycopg
from psycopg.types.json import Jsonb

# ---------- référentiels (contrôles de /predict) ----------

def facture_existe(conn, facture_id: str) -> bool:
    return conn.execute(
        "SELECT 1 AS x FROM factures WHERE facture_id = %s", (facture_id,)
    ).fetchone() is not None


def assure_existe(conn, assure_id: str) -> bool:
    return conn.execute(
        "SELECT 1 AS x FROM assures WHERE assure_id = %s", (assure_id,)
    ).fetchone() is not None


def prestataire_existe(conn, prestataire_id: str) -> bool:
    return conn.execute(
        "SELECT 1 AS x FROM prestataires WHERE prestataire_id = %s", (prestataire_id,)
    ).fetchone() is not None


def categorie_existe(conn, type_facture: str) -> bool:
    """type_facture doit être l'une des 9 catégories de garanties."""
    return conn.execute(
        "SELECT 1 AS x FROM garanties WHERE categorie = %s LIMIT 1", (type_facture,)
    ).fetchone() is not None


def lookup_codes(conn, codes: list[str]) -> dict[str, dict]:
    """Codes connus parmi actes et médicaments : {code: {type_ligne, libelle}} (équivaut à ref_codes)."""
    rows = conn.execute(
        "SELECT code_acte AS code, 'ACTE' AS type_ligne, libelle FROM referentiel_actes "
        "WHERE code_acte = ANY(%s) "
        "UNION ALL "
        "SELECT code_medicament, 'MEDICAMENT', libelle FROM referentiel_medicaments "
        "WHERE code_medicament = ANY(%s)",
        (codes, codes),
    ).fetchall()
    return {r["code"]: r for r in rows}


# ---------- configuration ----------

def get_seuil_alerte(conn, default: float) -> float:
    """Seuil modifiable en direct (table configuration) ; repli sur la valeur du .env."""
    try:
        with conn.transaction():  # savepoint : une erreur ici n'abîme pas la transaction
            row = conn.execute(
                "SELECT valeur FROM configuration WHERE cle = 'seuil_alerte'"
            ).fetchone()
        if row:
            return float(row["valeur"])
    except (psycopg.errors.UndefinedTable, ValueError):
        pass
    return default


# ---------- écriture facture / prédiction ----------

def insert_facture(conn, clean: dict, date_reception_defaut: date, calculation: dict | None = None,
                   status: str = "EN_COURS") -> None:
    """Enregistre une facture reçue par l'API.

    DÉCISION À VALIDER AVEC P1 : les colonnes de décision historique sont NOT NULL dans le
    contrat. Pour une facture neuve : statut EN_COURS, montant_pris_en_charge = 0,
    reste_a_charge = montant_total, montant_eligible = montant_total (pas encore calculé),
    date_traitement NULL. Canal et mode de règlement : valeurs par défaut si absents.
    """
    total = clean["montant_total"]
    calculation = calculation or {}
    eligible = calculation.get("montant_eligible", total)
    covered = calculation.get("montant_rembourse", 0)
    remaining = calculation.get("reste_a_charge", total)
    date_soin = date.fromisoformat(clean["date_soin"])
    date_facture = date.fromisoformat(clean["date_facture"]) if clean.get("date_facture") else date_soin
    date_reception = (
        date.fromisoformat(clean["date_reception"]) if clean.get("date_reception")
        else date_reception_defaut
    )
    conn.execute(
        "INSERT INTO factures (facture_id, numero_facture, prestataire_id, assure_id, contrat_id, "
        "ordonnance_id, type_facture, date_soin, heure_soin, date_facture, date_reception, "
        "canal_reception, mode_reglement, attestation_pec_id, entente_prealable_id, devise, "
        "nb_lignes, montant_total, montant_eligible, montant_pris_en_charge, reste_a_charge, "
        "statut, motif_rejet, date_traitement) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
        "%s, %s, %s, %s, NULL, NULL)",
        (
            clean["facture_id"], clean["numero_facture"], clean["prestataire_id"],
            clean["assure_id"], clean["contrat_id"], clean.get("ordonnance_id"),
            clean["type_facture"], date_soin, time.fromisoformat(clean["heure_soin"]),
            date_facture, date_reception,
            clean.get("canal_reception") or "PORTAIL_PRESTATAIRE",
            clean.get("mode_reglement") or "TIERS_PAYANT",
            clean.get("attestation_pec_id"), clean.get("entente_prealable_id"),
            clean["devise"], len(clean["lignes"]), total, eligible, covered, remaining, status,
        ),
    )
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO lignes_facture (ligne_id, facture_id, num_ligne, code, type_ligne, "
            "libelle, quantite, prix_unitaire, montant) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [
                (f"{clean['facture_id']}-L{ln['num_ligne']:02d}", clean["facture_id"],
                 ln["num_ligne"], ln["code"], ln["type_ligne"], ln["libelle"],
                 ln["quantite"], ln["prix_unitaire"], ln["montant"])
                for ln in clean["lignes"]
            ],
        )


def insert_calculation(conn, facture_id: str, calculation: dict) -> None:
    conn.execute(
        "INSERT INTO calculs_remboursement (facture_id, montant_reclame, montant_calcule, "
        "montant_rembourse, reste_a_charge, details) VALUES (%s, %s, %s, %s, %s, %s)",
        (facture_id, calculation["montant_reclame"], calculation["montant_calcule"],
         calculation["montant_rembourse"], calculation["reste_a_charge"],
         Jsonb(calculation.get("details", {}))),
    )


def insert_rejected_invoice(conn, raw: dict, errors: list[dict], user_id: int | str) -> None:
    conn.execute(
        "INSERT INTO factures_rejetees (facture_id, assure_id, prestataire_id, codes, details, "
        "utilisateur_id) VALUES (%s, %s, %s, %s, %s, %s)",
        (raw.get("facture_id"), raw.get("assure_id"), raw.get("prestataire_id"),
         Jsonb(sorted({e["code"] for e in errors})), Jsonb({"erreurs": errors}), user_id),
    )


def insert_prediction(conn, *, facture_id, nom_modele, version_modele, score, seuil,
                      est_alerte, latence_ms, variables, soumis_par) -> int:
    row = conn.execute(
        "INSERT INTO predictions (facture_id, nom_modele, version_modele, score, seuil_utilise, "
        "est_alerte, latence_ms, variables, soumis_par) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING prediction_id",
        (facture_id, nom_modele, version_modele, score, seuil, est_alerte, latence_ms,
         Jsonb(variables), soumis_par),
    ).fetchone()
    return row["prediction_id"]


def insert_shap(conn, prediction_id: int, facture_id: str, valeurs: dict) -> None:
    conn.execute(
        "INSERT INTO explications_shap (prediction_id, facture_id, valeurs) VALUES (%s, %s, %s)",
        (prediction_id, facture_id, Jsonb(valeurs)),
    )


# ---------- alertes et décisions ----------

_DERNIERE_DECISION = (
    "LEFT JOIN LATERAL (SELECT decision, decided_at AS date_decision FROM decisions_gestionnaires "
    "WHERE prediction_id = p.prediction_id ORDER BY decided_at DESC, decision_id DESC "
    "LIMIT 1) d ON TRUE"
)


def _alert_filter_sql(statut: str, priorite: str | None, type_alerte: str | None) -> tuple[str, list]:
    where = ["p.est_alerte"]
    params = []
    if statut in {"en_attente", "EN_ATTENTE"}:
        where.append("d.decision IS NULL")
    elif statut in {"traitees", "TRAITEE", "VALIDEE", "REJETEE", "ESCALADEE"}:
        where.append("d.decision IS NOT NULL")
        decisions = {
            "VALIDEE": ("VALIDER", "valide"),
            "REJETEE": ("REJETER", "CONFIRMER_FRAUDE", "rejete", "fraude_confirmee", "faux_positif"),
            "ESCALADEE": ("ESCALADER", "a_investiguer"),
        }
        if statut in decisions:
            values = decisions[statut]
            where.append("d.decision IN (" + ", ".join(["%s"] * len(values)) + ")")
            params.extend(values)
    elif statut not in {"toutes", "TOUTES"}:
        raise ValueError("Statut d'alerte invalide")
    if priorite:
        where.append("a.priorite = %s")
        params.append(priorite)
    if type_alerte:
        where.append("a.type = %s")
        params.append(type_alerte)
    return " AND ".join(where), params


def list_alertes(conn, statut: str = "EN_ATTENTE", limit: int = 50, offset: int = 0,
                 priorite: str | None = None, type_alerte: str | None = None,
                 tri: str = "priorite") -> list[dict]:
    where, params = _alert_filter_sql(statut, priorite, type_alerte)
    order = {
        "priorite": "CASE a.priorite WHEN 'HAUTE' THEN 0 WHEN 'MOYENNE' THEN 1 ELSE 2 END, p.date DESC",
        "date": "p.date DESC",
        "score": "p.score DESC, p.date DESC",
    }.get(tri)
    if order is None:
        raise ValueError("Tri d'alerte invalide")
    return conn.execute(
        "SELECT p.facture_id, p.score, p.version_modele, p.date, f.montant_total, "
        "a.type, a.priorite, a.codes, a.etat_notification, a.tentatives_notification, "
        "CASE WHEN d.decision IS NULL THEN 'EN_ATTENTE' "
        "WHEN d.decision IN ('VALIDER', 'valide') THEN 'VALIDEE' "
        "WHEN d.decision IN ('REJETER', 'CONFIRMER_FRAUDE', 'rejete', 'fraude_confirmee', 'faux_positif') THEN 'REJETEE' "
        "ELSE 'ESCALADEE' END AS statut, "
        "(SELECT count(*) FROM alertes_prescription ar WHERE ar.prediction_id = p.prediction_id) "
        "AS nb_regles, "
        "d.decision AS derniere_decision, d.date_decision "
        "FROM predictions p JOIN factures f ON f.facture_id = p.facture_id "
        "JOIN alertes a ON a.facture_id = p.facture_id "
        f"{_DERNIERE_DECISION} WHERE {where} ORDER BY {order} LIMIT %s OFFSET %s",
        (*params, limit, offset),
    ).fetchall()


def count_alertes(conn, statut: str, priorite: str | None = None,
                  type_alerte: str | None = None) -> int:
    where, params = _alert_filter_sql(statut, priorite, type_alerte)
    row = conn.execute(
        "SELECT count(*) AS n FROM predictions p JOIN alertes a ON a.facture_id = p.facture_id "
        f"{_DERNIERE_DECISION} WHERE {where}", params
    ).fetchone()
    return int(row["n"])


def get_prediction(conn, facture_id: str, for_update: bool = False) -> dict | None:
    lock = " FOR UPDATE" if for_update else ""
    return conn.execute(
        "SELECT prediction_id, facture_id, nom_modele, version_modele, score, seuil_utilise, "
        "est_alerte, date FROM predictions WHERE facture_id = %s" + lock,
        (facture_id,),
    ).fetchone()


def get_shap(conn, prediction_id: int) -> dict | None:
    return conn.execute(
        "SELECT valeurs FROM explications_shap WHERE prediction_id = %s", (prediction_id,)
    ).fetchone()


def list_decisions(conn, prediction_id: int) -> list[dict]:
    return conn.execute(
        "SELECT decision_id, facture_id, user_id::bigint AS gestionnaire_id, decision, commentaire, "
        "montant_economise, decided_at AS date_decision FROM decisions_gestionnaires "
        "WHERE prediction_id = %s ORDER BY decided_at DESC, decision_id DESC",
        (prediction_id,),
    ).fetchall()


def insert_decision(conn, *, prediction_id, facture_id, gestionnaire_id, decision,
                    commentaire, montant_economise) -> dict:
    return conn.execute(
        "INSERT INTO decisions_gestionnaires (prediction_id, facture_id, user_id, decision, "
        "commentaire, montant_economise) VALUES (%s, %s, %s, %s, %s, %s) "
        "RETURNING decision_id, facture_id, user_id::bigint AS gestionnaire_id, decision, commentaire, "
        "montant_economise, decided_at AS date_decision",
        (prediction_id, facture_id, str(gestionnaire_id), decision, commentaire, montant_economise),
    ).fetchone()


def get_alert_summary(conn, facture_id: str) -> dict | None:
    return conn.execute(
        "SELECT p.facture_id, p.score, p.version_modele, p.date, f.montant_total, "
        "a.type, a.priorite, a.codes, a.etat_notification, a.tentatives_notification, "
        "(SELECT count(*) FROM alertes_prescription ar WHERE ar.prediction_id = p.prediction_id) AS nb_regles, "
        "CASE WHEN d.decision IS NULL THEN 'EN_ATTENTE' "
        "WHEN d.decision IN ('VALIDER', 'valide') THEN 'VALIDEE' "
        "WHEN d.decision IN ('REJETER', 'CONFIRMER_FRAUDE', 'rejete', 'fraude_confirmee', 'faux_positif') THEN 'REJETEE' "
        "ELSE 'ESCALADEE' END AS statut, d.decision AS derniere_decision, d.date_decision "
        "FROM predictions p JOIN factures f ON f.facture_id = p.facture_id "
        "JOIN alertes a ON a.facture_id = p.facture_id "
        f"{_DERNIERE_DECISION} WHERE p.facture_id = %s AND p.est_alerte",
        (facture_id,),
    ).fetchone()


def decision_existe(conn, prediction_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 AS existe FROM decisions_gestionnaires WHERE prediction_id = %s LIMIT 1",
        (prediction_id,),
    ).fetchone()
    return row is not None


def update_facture_status(conn, facture_id: str, status: str) -> None:
    conn.execute(
        "UPDATE factures SET statut = %s, date_traitement = CURRENT_DATE WHERE facture_id = %s",
        (status, facture_id),
    )


def update_alert_notification(conn, facture_id: str, state: str, attempts: int) -> None:
    conn.execute(
        "UPDATE alertes SET etat_notification = %s, tentatives_notification = %s "
        "WHERE facture_id = %s",
        (state, attempts, facture_id),
    )


def get_alert_invoice(conn, facture_id: str) -> dict:
    row = conn.execute(
        "SELECT facture_id, numero_facture, type_facture, date_soin, montant_total, "
        "devise, statut FROM factures WHERE facture_id = %s", (facture_id,),
    ).fetchone()
    return dict(row) if row else {}


# ---------- identités (déchiffrement réservé à l'affichage d'une alerte) ----------

def get_assure_de_facture(conn, facture_id: str) -> str | None:
    row = conn.execute(
        "SELECT assure_id FROM factures WHERE facture_id = %s", (facture_id,)
    ).fetchone()
    return row["assure_id"] if row else None


def get_identite_chiffree(conn, assure_id: str):
    row = conn.execute(
        "SELECT donnees_chiffrees FROM identites_chiffrees WHERE assure_id = %s", (assure_id,)
    ).fetchone()
    return row["donnees_chiffrees"] if row else None


# ---------- alertes de règles de prescription (P3-16) ----------

def insert_alertes_regles(conn, prediction_id: int, facture_id: str, findings) -> None:
    if not findings:
        return
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO alertes_prescription (prediction_id, facture_id, regle_code, severite, "
            "message, details) VALUES (%s, %s, %s, %s, %s, %s)",
            [(prediction_id, facture_id, f.regle_code, f.severite, f.message, Jsonb(f.details))
             for f in findings],
        )


def insert_prescription_alerts(conn, ordonnance_id: str, findings, utilisateur_id: int) -> None:
    if not findings:
        return
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO alertes_prescription "
            "(prediction_id, facture_id, ordonnance_id, type_alerte, regle_code, severite, message, details, utilisateur_id) "
            "VALUES (NULL, NULL, %s, 'PRESCRIPTION', %s, 'HAUTE', %s, %s, %s)",
            [(ordonnance_id, f.code, f.libelle, Jsonb(f.details), utilisateur_id) for f in findings],
        )


def insert_alert(conn, *, facture_id: str, codes: list[str], priority: str = "MOYENNE") -> int:
    row = conn.execute(
        "INSERT INTO alertes (facture_id, type, priorite, codes) VALUES (%s, 'FRAUDE', %s, %s) "
        "RETURNING alerte_id",
        (facture_id, priority, Jsonb(codes)),
    ).fetchone()
    return row["alerte_id"] if row else 0


def list_alertes_regles(conn, prediction_id: int) -> list[dict]:
    return conn.execute(
        "SELECT alerte_regle_id, regle_code, severite, message, details, cree_le "
        "FROM alertes_prescription WHERE prediction_id = %s ORDER BY alerte_regle_id",
        (prediction_id,),
    ).fetchall()


# ---------- KPI (P3-15) ----------

def kpi_summary(conn, jours: int) -> dict:
    """Agrégats sur la période (jours derniers jours). Aucune donnée personnelle."""
    row = conn.execute(
        "SELECT count(*) AS factures_scorees, "
        "count(*) FILTER (WHERE p.est_alerte) AS alertes_total, "
        "count(*) FILTER (WHERE p.est_alerte AND d.decision IS NULL) AS alertes_en_attente, "
        "count(*) FILTER (WHERE d.decision IS NOT NULL) AS alertes_traitees, "
        "count(*) FILTER (WHERE d.decision = 'fraude_confirmee') AS fraudes_confirmees, "
        "count(*) FILTER (WHERE d.decision = 'faux_positif') AS faux_positifs, "
        "count(*) FILTER (WHERE d.decision = 'a_investiguer') AS a_investiguer, "
        "COALESCE(sum(f.montant_total) FILTER (WHERE p.est_alerte AND d.decision IS NULL), 0) "
        "AS montant_en_attente, "
        "COALESCE(sum(f.montant_total) FILTER (WHERE d.decision = 'fraude_confirmee'), 0) "
        "AS montant_fraude_confirmee, "
        "COALESCE(avg(p.score), 0) AS score_moyen "
        "FROM predictions p JOIN factures f ON f.facture_id = p.facture_id "
        f"{_DERNIERE_DECISION} "
        "WHERE p.date >= now() - make_interval(days => %s)",
        (jours,),
    ).fetchone()
    return dict(row)


def kpi_economies(conn, jours: int) -> int:
    """Somme des montants économisés saisis par les gestionnaires (dernière décision de chaque alerte)."""
    row = conn.execute(
        "SELECT COALESCE(sum(d.montant_economise), 0) AS total "
        "FROM predictions p JOIN LATERAL (SELECT decision, montant_economise "
        "FROM decisions_gestionnaire WHERE prediction_id = p.prediction_id "
        "ORDER BY date_decision DESC, decision_id DESC LIMIT 1) d ON TRUE "
        "WHERE d.decision = 'fraude_confirmee' AND p.date >= now() - make_interval(days => %s)",
        (jours,),
    ).fetchone()
    return int(row["total"])


def kpi_par_jour(conn, jours: int) -> list[dict]:
    return conn.execute(
        "SELECT p.date::date AS jour, count(*) AS factures, "
        "count(*) FILTER (WHERE p.est_alerte) AS alertes "
        "FROM predictions p WHERE p.date >= now() - make_interval(days => %s) "
        "GROUP BY 1 ORDER BY 1",
        (jours,),
    ).fetchall()


def kpi_regles(conn, jours: int) -> list[dict]:
    return conn.execute(
        "SELECT regle_code, count(*) AS n FROM alertes_prescription "
        "WHERE cree_le >= now() - make_interval(days => %s) GROUP BY 1 ORDER BY n DESC",
        (jours,),
    ).fetchall()


# ---------- configuration modifiable (P3-17) ----------

def set_config(conn, cle: str, valeur: str, par: str) -> None:
    conn.execute(
        "INSERT INTO configuration (cle, valeur, mis_a_jour_le, mis_a_jour_par) "
        "VALUES (%s, %s, now(), %s) "
        "ON CONFLICT (cle) DO UPDATE SET valeur = EXCLUDED.valeur, "
        "mis_a_jour_le = now(), mis_a_jour_par = EXCLUDED.mis_a_jour_par",
        (cle, valeur, par),
    )


def get_config_row(conn, cle: str) -> dict | None:
    return conn.execute(
        "SELECT cle, valeur, mis_a_jour_le, mis_a_jour_par FROM configuration WHERE cle = %s",
        (cle,),
    ).fetchone()


def get_config_values(conn, keys: list[str]) -> dict[str, dict]:
    rows = conn.execute(
        "SELECT cle, valeur, mis_a_jour_le, mis_a_jour_par "
        "FROM configuration WHERE cle = ANY(%s)",
        (keys,),
    ).fetchall()
    return {row["cle"]: row for row in rows}


def list_audit(conn, type_evenement: str | None, limit: int, offset: int) -> list[dict]:
    where, params = "", []
    if type_evenement:
        where, params = "WHERE type_evenement = %s", [type_evenement]
    return conn.execute(
        "SELECT audit_id, horodatage, type_evenement, utilisateur_id, type_entite, entite_id, "
        "nom_modele, version_modele, entree, sortie FROM journal_audit "
        f"{where} ORDER BY audit_id DESC LIMIT %s OFFSET %s",
        (*params, limit, offset),
    ).fetchall()


def rollback_target(conn, current_version: str, limit: int = 50) -> str | None:
    """Version à restaurer : celle qui était active avant l'activation de la version courante.

    S'appuie sur le journal d'audit (événements `modele_charge`, champ previous_version).
    """
    rows = conn.execute(
        "SELECT entree->>'previous_version' AS prev, sortie->>'active_version' AS v "
        "FROM journal_audit WHERE type_evenement = 'modele_charge' "
        "ORDER BY audit_id DESC LIMIT %s",
        (limit,),
    ).fetchall()
    for r in rows:
        if r["v"] == current_version and r["prev"] and r["prev"] != current_version:
            return r["prev"]
    return None


# ---------- métriques et dérive (P3-18 / P3-19) ----------

def metrics_predictions(conn, hours: int) -> dict:
    row = conn.execute(
        "SELECT count(*) AS volume, count(*) FILTER (WHERE est_alerte) AS alertes, "
        "percentile_cont(0.5) WITHIN GROUP (ORDER BY latence_ms) AS p50, "
        "percentile_cont(0.95) WITHIN GROUP (ORDER BY latence_ms) AS p95, "
        "max(latence_ms) AS max_latence "
        "FROM predictions WHERE date >= now() - make_interval(hours => %s)",
        (hours,),
    ).fetchone()
    return dict(row)


def metrics_audit_counts(conn, hours: int) -> dict[str, int]:
    rows = conn.execute(
        "SELECT type_evenement, count(*) AS n FROM journal_audit "
        "WHERE horodatage >= now() - make_interval(hours => %s) GROUP BY 1",
        (hours,),
    ).fetchall()
    return {r["type_evenement"]: int(r["n"]) for r in rows}


def drift_reference_variables(conn, size: int) -> list[dict]:
    """Référence = les `size` premières prédictions (distribution de départ)."""
    rows = conn.execute(
        "SELECT variables FROM predictions WHERE variables IS NOT NULL "
        "ORDER BY prediction_id ASC LIMIT %s", (size,)
    ).fetchall()
    return [r["variables"] for r in rows]


def drift_current_variables(conn, days: int, skip_first: int) -> list[dict]:
    """Courant = prédictions des `days` derniers jours, hors échantillon de référence."""
    rows = conn.execute(
        "SELECT variables FROM predictions WHERE variables IS NOT NULL "
        "AND date >= now() - make_interval(days => %s) "
        "AND prediction_id > (SELECT COALESCE(max(prediction_id), 0) FROM ("
        "  SELECT prediction_id FROM predictions ORDER BY prediction_id ASC LIMIT %s) r) "
        "ORDER BY prediction_id ASC",
        (days, skip_first),
    ).fetchall()
    return [r["variables"] for r in rows]


def recent_shap_importance(conn, limit: int = 300) -> dict[str, float]:
    """Importance moyenne |SHAP| par variable (sur les dernières explications)."""
    rows = conn.execute(
        "SELECT valeurs->'toutes' AS toutes FROM explications_shap "
        "ORDER BY prediction_id DESC LIMIT %s", (limit,)
    ).fetchall()
    sums: dict[str, float] = {}
    n = 0
    for r in rows:
        toutes = r["toutes"]
        if not isinstance(toutes, dict):
            continue
        n += 1
        for k, v in toutes.items():
            try:
                sums[k] = sums.get(k, 0.0) + abs(float(v))
            except (TypeError, ValueError):
                continue
    return {k: v / n for k, v in sums.items()} if n else {}
