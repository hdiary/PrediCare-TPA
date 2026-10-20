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
    """Codes connus parmi actes et médicaments : {code: {type_ligne, libelle}}.

    Équivaut à ref_codes.
    """
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
    date_facture = (
        date.fromisoformat(clean["date_facture"]) if clean.get("date_facture") else date_soin
    )
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
            "libelle, quantite, prix_unitaire, montant) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
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
    "LEFT JOIN LATERAL (SELECT decision, date_decision FROM decisions_gestionnaire "
    "WHERE prediction_id = p.prediction_id ORDER BY date_decision DESC, decision_id DESC "
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
        "f.prestataire_id, f.assure_id, "
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


def list_prescription_alerts(
    conn, rule: str | None = None, min_severity: int = 0
) -> list[dict]:
    filters = ["ap.type_alerte = 'PRESCRIPTION'", "ap.ordonnance_id IS NOT NULL"]
    params: list[object] = []
    if rule:
        filters.append("ap.regle_code = %s")
        params.append(rule)
    if min_severity:
        filters.append(
            "CASE ap.severite WHEN 'HAUTE' THEN 3 "
            "WHEN 'MOYENNE' THEN 2 ELSE 1 END >= %s"
        )
        params.append(min_severity)
    return conn.execute(
        "SELECT ap.alerte_regle_id::text AS id, ap.ordonnance_id AS prescription_id, "
        "ap.regle_code AS rule, "
        "CASE ap.severite WHEN 'HAUTE' THEN 3 WHEN 'MOYENNE' THEN 2 ELSE 1 END AS severity, "
        "ap.message AS detail, o.diagnostic AS diagnosis, "
        "o.date_prescription AS prescription_date, "
        "o.prescripteur_id AS prescriber_pseudo, o.assure_id AS insured_pseudo "
        "FROM alertes_prescription ap "
        "JOIN ordonnances o ON o.ordonnance_id = ap.ordonnance_id "
        f"WHERE {' AND '.join(filters)} "
        "ORDER BY severity DESC, ap.cree_le DESC, ap.alerte_regle_id DESC",
        params,
    ).fetchall()


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
        "SELECT decision_id, facture_id, gestionnaire_id, decision, commentaire, "
        "montant_economise, date_decision FROM decisions_gestionnaire "
        "WHERE prediction_id = %s ORDER BY date_decision DESC, decision_id DESC",
        (prediction_id,),
    ).fetchall()


def insert_decision(conn, *, prediction_id, facture_id, gestionnaire_id, decision,
                    commentaire, montant_economise) -> dict:
    return conn.execute(
        "INSERT INTO decisions_gestionnaire (prediction_id, facture_id, gestionnaire_id, decision, "
        "commentaire, montant_economise) VALUES (%s, %s, %s, %s, %s, %s) "
        "RETURNING decision_id, facture_id, gestionnaire_id, decision, commentaire, "
        "montant_economise, date_decision",
        (prediction_id, facture_id, gestionnaire_id, decision, commentaire, montant_economise),
    ).fetchone()


def get_alert_summary(conn, facture_id: str) -> dict | None:
    return conn.execute(
        "SELECT p.facture_id, p.score, p.version_modele, p.date, f.montant_total, "
        "f.prestataire_id, f.assure_id, "
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
        "SELECT 1 AS existe FROM decisions_gestionnaire WHERE prediction_id = %s LIMIT 1",
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


# ---------- comptes utilisateurs ----------

_COLS_UTILISATEUR = (
    "utilisateur_id, identifiant, email, role, assure_id, prestataire_id, actif, "
    "derniere_connexion, mot_de_passe_hash, tentatives_echouees, verrouille_jusqua"
)
_CHAMPS_MODIFIABLES = {"identifiant", "role", "assure_id", "prestataire_id", "actif"}


def list_alertes_regles(conn, prediction_id: int) -> list[dict]:
    return conn.execute(
        "SELECT alerte_regle_id, regle_code, severite, message, details, cree_le "
        "FROM alertes_prescription WHERE prediction_id = %s "
        "ORDER BY cree_le, alerte_regle_id",
        (prediction_id,),
    ).fetchall()


_USER_SELECT = (
    "u.utilisateur_id, u.identifiant, u.nom_utilisateur AS email, r.nom_role AS role, "
    "u.assure_id, u.prestataire_id, u.est_actif AS actif, "
    "u.derniere_connexion, u.tentatives_echouees, u.verrouille_jusqua"
)
_USER_FROM = (
    "FROM utilisateurs u "
    "JOIN utilisateurs_roles ur ON ur.utilisateur_id = u.utilisateur_id "
    "JOIN roles r ON r.role_id = ur.role_id"
)
_CHAMPS_MODIFIABLES = {"identifiant", "role", "assure_id", "prestataire_id", "actif"}


def list_utilisateurs(conn, *, role: str | None, actif: bool | None, q: str | None,
                      limit: int, offset: int) -> list[dict]:
    clauses = []
    params = []
    if role is not None:
        clauses.append("r.nom_role = %s")
        params.append(role)
    if actif is not None:
        clauses.append("u.est_actif = %s")
        params.append(actif)
    if q:
        clauses.append("(u.nom_utilisateur ILIKE %s OR u.identifiant ILIKE %s)")
        params.extend((f"%{q}%", f"%{q}%"))
    where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
    params.extend((limit, offset))
    return conn.execute(
        f"SELECT {_USER_SELECT} {_USER_FROM} {where}"
        "ORDER BY u.utilisateur_id LIMIT %s OFFSET %s",
        params,
    ).fetchall()


def count_utilisateurs(conn, *, role: str | None, actif: bool | None,
                       q: str | None) -> int:
    clauses = []
    params = []
    if role is not None:
        clauses.append("r.nom_role = %s")
        params.append(role)
    if actif is not None:
        clauses.append("u.est_actif = %s")
        params.append(actif)
    if q:
        clauses.append("(u.nom_utilisateur ILIKE %s OR u.identifiant ILIKE %s)")
        params.extend((f"%{q}%", f"%{q}%"))
    where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
    row = conn.execute(
        f"SELECT count(*) AS total {_USER_FROM} {where}",
        params,
    ).fetchone()
    return row["total"]


def get_utilisateur(conn, user_id: int) -> dict | None:
    return conn.execute(
        f"SELECT {_USER_SELECT} {_USER_FROM} WHERE u.utilisateur_id = %s", (user_id,)
    ).fetchone()


def get_utilisateur_par_email(conn, email: str) -> dict | None:
    return conn.execute(
        f"SELECT {_USER_SELECT} {_USER_FROM} "
        "WHERE lower(u.nom_utilisateur) = lower(%s)",
        (email,),
    ).fetchone()


def get_mot_de_passe_hash(conn, user_id: int) -> str | None:
    row = conn.execute(
        "SELECT hash_mot_de_passe FROM utilisateurs WHERE utilisateur_id = %s", (user_id,)
    ).fetchone()
    return row["hash_mot_de_passe"] if row else None


def create_utilisateur(conn, *, email: str, password_hash: str, role: str,
                       assure_id: str | None, prestataire_id: str | None,
                       actif: bool, identifiant: str | None = None) -> dict | None:
    """Crée un compte ; retourne None si le nom d'utilisateur existe déjà."""
    role_row = conn.execute(
        "SELECT role_id FROM roles WHERE nom_role = %s", (role,)
    ).fetchone()
    if role_row is None:
        raise ValueError(f"Rôle inconnu : {role}")
    created = conn.execute(
        "INSERT INTO utilisateurs "
        "(identifiant, nom_utilisateur, hash_mot_de_passe, assure_id, prestataire_id, est_actif) "
        "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING "
        "RETURNING utilisateur_id",
        (identifiant, email, password_hash, assure_id, prestataire_id, actif),
    ).fetchone()
    if created is None:
        return None
    conn.execute(
        "INSERT INTO utilisateurs_roles (utilisateur_id, role_id) VALUES (%s, %s)",
        (created["utilisateur_id"], role_row["role_id"]),
    )
    return get_utilisateur(conn, created["utilisateur_id"])


def update_utilisateur(conn, user_id: int, champs: dict) -> dict | None:
    """Met à jour les seuls champs autorisés (noms de colonnes jamais issus du client)."""
    inconnus = set(champs) - _CHAMPS_MODIFIABLES
    if inconnus:
        raise ValueError(f"Champs non modifiables : {sorted(inconnus)}")
    if not champs:
        return get_utilisateur(conn, user_id)
    if "role" in champs:
        role_row = conn.execute(
            "SELECT role_id FROM roles WHERE nom_role = %s", (champs["role"],)
        ).fetchone()
        if role_row is None:
            raise ValueError(f"Rôle inconnu : {champs['role']}")
        conn.execute(
            "DELETE FROM utilisateurs_roles WHERE utilisateur_id = %s", (user_id,)
        )
        conn.execute(
            "INSERT INTO utilisateurs_roles (utilisateur_id, role_id) VALUES (%s, %s)",
            (user_id, role_row["role_id"]),
        )
    columns = {
        "identifiant": "identifiant",
        "assure_id": "assure_id",
        "prestataire_id": "prestataire_id",
        "actif": "est_actif",
    }
    assignments = {columns[key]: value for key, value in champs.items() if key in columns}
    if assignments:
        sets = ", ".join(f"{column} = %s" for column in assignments)
        conn.execute(
            f"UPDATE utilisateurs SET {sets} WHERE utilisateur_id = %s",
            [*assignments.values(), user_id],
        )
    return get_utilisateur(conn, user_id)


def set_mot_de_passe(conn, user_id: int, password_hash: str) -> None:
    """Change le mot de passe et lève un éventuel verrouillage de connexion."""
    conn.execute(
        "UPDATE utilisateurs SET hash_mot_de_passe = %s, tentatives_echouees = 0, "
        "verrouille_jusqua = NULL WHERE utilisateur_id = %s",
        (password_hash, user_id),
    )


def deverrouiller_utilisateur(conn, user_id: int) -> bool:
    cur = conn.execute(
        "UPDATE utilisateurs SET tentatives_echouees = 0, verrouille_jusqua = NULL "
        "WHERE utilisateur_id = %s",
        (user_id,),
    )
    return cur.rowcount > 0


def est_verrouille(conn, user_id: int) -> bool:
    row = conn.execute(
        "SELECT (verrouille_jusqua IS NOT NULL AND verrouille_jusqua > now()) AS v "
        "FROM utilisateurs WHERE utilisateur_id = %s",
        (user_id,),
    ).fetchone()
    return bool(row and row["v"])


def enregistrer_echec_mot_de_passe(conn, user_id: int, max_tentatives: int,
                                   minutes_verrou: int) -> None:
    """Même compteur que la connexion : après N échecs, le compte est verrouillé."""
    conn.execute(
        "UPDATE utilisateurs SET "
        "tentatives_echouees = CASE WHEN tentatives_echouees + 1 >= %s "
        "THEN 0 ELSE tentatives_echouees + 1 END, "
        "verrouille_jusqua = CASE WHEN tentatives_echouees + 1 >= %s "
        "THEN now() + make_interval(mins => %s) ELSE verrouille_jusqua END "
        "WHERE utilisateur_id = %s",
        (max_tentatives, max_tentatives, minutes_verrou, user_id),
    )


# ---------- jetons de réinitialisation de mot de passe ----------
# Seul le hachage SHA-256 du jeton est stocké : une fuite de la base ne donne aucun lien valide.
# La table est créée à la première utilisation si les migrations ne l'ont pas déjà fait
# (voir aussi api/sql/001_reinitialisations_mdp.sql).

_reset_table_ready = False


def ensure_reset_table(conn) -> None:
    global _reset_table_ready
    if _reset_table_ready:
        return
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS reinitialisations_mdp ("
            "reset_id BIGSERIAL PRIMARY KEY, "
            "utilisateur_id BIGINT NOT NULL REFERENCES utilisateurs(utilisateur_id) "
            "ON DELETE CASCADE, "
            "token_hash TEXT NOT NULL UNIQUE, "
            "cree_le TIMESTAMPTZ NOT NULL DEFAULT now(), "
            "expire_le TIMESTAMPTZ NOT NULL, "
            "utilise_le TIMESTAMPTZ)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_reinitialisations_mdp_utilisateur "
            "ON reinitialisations_mdp (utilisateur_id)"
        )
        conn.commit()   # le DDL ne doit pas être annulé par un échec ultérieur de la requête
    except (psycopg.errors.DuplicateTable, psycopg.errors.UniqueViolation,
            psycopg.errors.DuplicateObject):
        conn.rollback()   # un autre processus l'a créée en même temps
    _reset_table_ready = True


def compter_demandes_reinitialisation(conn, user_id: int, minutes: int = 60) -> int:
    ensure_reset_table(conn)
    return conn.execute(
        "SELECT count(*) AS n FROM reinitialisations_mdp "
        "WHERE utilisateur_id = %s AND cree_le > now() - make_interval(mins => %s)",
        (user_id, minutes),
    ).fetchone()["n"]


def creer_jeton_reinitialisation(conn, user_id: int, token_hash: str, ttl_minutes: int) -> None:
    """Enregistre un nouveau jeton et invalide les précédents du même compte."""
    ensure_reset_table(conn)
    conn.execute(
        "UPDATE reinitialisations_mdp SET utilise_le = now() "
        "WHERE utilisateur_id = %s AND utilise_le IS NULL",
        (user_id,),
    )
    conn.execute(
        "DELETE FROM reinitialisations_mdp WHERE expire_le < now() - interval '7 days'"
    )
    conn.execute(
        "INSERT INTO reinitialisations_mdp (utilisateur_id, token_hash, expire_le) "
        "VALUES (%s, %s, now() + make_interval(mins => %s))",
        (user_id, token_hash, ttl_minutes),
    )


def consommer_jeton_reinitialisation(conn, token_hash: str) -> int | None:
    """Usage unique et atomique : retourne l'utilisateur si le jeton est valide, sinon None."""
    ensure_reset_table(conn)
    row = conn.execute(
        "UPDATE reinitialisations_mdp SET utilise_le = now() "
        "WHERE token_hash = %s AND utilise_le IS NULL AND expire_le > now() "
        "RETURNING utilisateur_id",
        (token_hash,),
    ).fetchone()


def get_config_values(conn, keys: list[str]) -> dict[str, dict]:
    rows = conn.execute(
        "SELECT cle, valeur, mis_a_jour_le, mis_a_jour_par "
        "FROM configuration WHERE cle = ANY(%s)",
        (keys,),
    ).fetchall()
    return {row["cle"]: row for row in rows}


def list_audit(
    conn,
    event_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    where, params = "", []
    if event_type:
        where, params = "WHERE a.type_evenement = %s", [event_type]
    return conn.execute(
        "SELECT a.horodatage AS date, a.type_evenement, a.utilisateur_id, "
        "(SELECT r.nom_role FROM utilisateurs_roles ur "
        "JOIN roles r ON r.role_id = ur.role_id "
        "WHERE ur.utilisateur_id = a.utilisateur_id "
        "ORDER BY r.role_id LIMIT 1) AS role_acteur, "
        "a.type_entite, a.entite_id, a.version_modele "
        "FROM journal_audit a "
        f"{where} ORDER BY a.horodatage DESC, a.audit_id DESC LIMIT %s OFFSET %s",
        (*params, limit, offset),
    ).fetchall()

# ---------- référentiels pour pdf_extract ----------

def load_reference_tables(conn) -> dict:
    """Charge les 3 tables nécessaires à pdf_extract.build_reference()."""
    rows_actes = conn.execute(
        "SELECT code_acte AS code, libelle FROM referentiel_actes"
    ).fetchall()
    rows_meds = conn.execute(
        "SELECT code_medicament AS code, libelle FROM referentiel_medicaments"
    ).fetchall()
    rows_prestataires = conn.execute(
        "SELECT prestataire_id, nom, nif, numero_onm FROM prestataires"
    ).fetchall()

    return {
        "referentiel_actes": [dict(r) for r in rows_actes],
        "referentiel_medicaments": [dict(r) for r in rows_meds],
        "prestataires": [dict(r) for r in rows_prestataires],
    }
    """Charge les 3 tables nécessaires à pdf_extract.build_reference().

    Seul endroit qui connaît les colonnes utilisées par l'extraction PDF :
      - referentiel_actes(code_acte, libelle)
      - referentiel_medicaments(code_medicament, libelle)
      - prestataires(prestataire_id, nom, nif, numero_onm)
    """
    rows_actes = conn.execute(
        "SELECT code_acte AS code, libelle FROM referentiel_actes"
    ).fetchall()
    rows_meds = conn.execute(
        "SELECT code_medicament AS code, libelle FROM referentiel_medicaments"
    ).fetchall()
    rows_prestataires = conn.execute(
        "SELECT prestataire_id, nom, nif, numero_onm FROM prestataires"
    ).fetchall()

    return {
        "referentiel_actes":    [dict(r) for r in rows_actes],
        "referentiel_medicaments": [dict(r) for r in rows_meds],
        "prestataires":         [dict(r) for r in rows_prestataires],
    }


def contrat_de_assure(conn, assure_id: str) -> str | None:
    """Contrat auquel est rattaché l'assuré (le PDF de facture ne le mentionne pas)."""
    row = conn.execute(
        "SELECT contrat_id FROM assures WHERE assure_id = %s", (assure_id,)
    ).fetchone()
    return row["contrat_id"] if row else None