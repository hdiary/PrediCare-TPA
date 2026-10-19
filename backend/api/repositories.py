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

def insert_facture(conn, clean: dict, date_reception_defaut: date) -> None:
    """Enregistre une facture reçue par l'API.

    DÉCISION À VALIDER AVEC P1 : les colonnes de décision historique sont NOT NULL dans le
    contrat. Pour une facture neuve : statut EN_COURS, montant_pris_en_charge = 0,
    reste_a_charge = montant_total, montant_eligible = montant_total (pas encore calculé),
    date_traitement NULL. Canal et mode de règlement : valeurs par défaut si absents.
    """
    total = clean["montant_total"]
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
        "%s, "
        "0, %s, 'EN_COURS', NULL, NULL)",
        (
            clean["facture_id"], clean["numero_facture"], clean["prestataire_id"],
            clean["assure_id"], clean["contrat_id"], clean.get("ordonnance_id"),
            clean["type_facture"], date_soin, time.fromisoformat(clean["heure_soin"]),
            date_facture, date_reception,
            clean.get("canal_reception") or "PORTAIL_PRESTATAIRE",
            clean.get("mode_reglement") or "TIERS_PAYANT",
            clean.get("attestation_pec_id"), clean.get("entente_prealable_id"),
            clean["devise"], len(clean["lignes"]), total, total, total,
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


def list_alertes(conn, statut: str, limit: int, offset: int) -> list[dict]:
    where = "WHERE p.est_alerte"
    if statut == "en_attente":
        where += " AND d.decision IS NULL"
    elif statut == "traitees":
        where += " AND d.decision IS NOT NULL"
    return conn.execute(
        "SELECT p.facture_id, p.score, p.version_modele, p.date, f.montant_total, "
        "f.prestataire_id, f.assure_id, f.type_facture, "
        "d.decision AS derniere_decision, d.date_decision "
        "FROM predictions p JOIN factures f ON f.facture_id = p.facture_id "
        f"{_DERNIERE_DECISION} {where} ORDER BY p.date DESC LIMIT %s OFFSET %s",
        (limit, offset),
    ).fetchall()


def get_prediction(conn, facture_id: str) -> dict | None:
    return conn.execute(
        "SELECT prediction_id, facture_id, nom_modele, version_modele, score, seuil_utilise, "
        "est_alerte, date FROM predictions WHERE facture_id = %s",
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


# ---------- contexte facture (détail d'alerte, listes) ----------

def get_facture_et_lignes(conn, facture_id: str) -> tuple[dict | None, list[dict]]:
    facture = conn.execute(
        "SELECT facture_id, numero_facture, prestataire_id, assure_id, contrat_id, type_facture, "
        "date_soin, devise, nb_lignes, montant_total FROM factures WHERE facture_id = %s",
        (facture_id,),
    ).fetchone()
    lignes = conn.execute(
        "SELECT num_ligne, code, type_ligne, libelle, quantite, prix_unitaire, montant "
        "FROM lignes_facture WHERE facture_id = %s ORDER BY num_ligne",
        (facture_id,),
    ).fetchall()
    return facture, lignes


def list_factures(conn, *, prestataire_id: str | None, assure_id: str | None,
                  statut: str | None, limit: int, offset: int) -> tuple[list[dict], int]:
    """Factures visibles par l'appelant (le filtre de périmètre est posé par le routeur)."""
    where, params = [], []
    if prestataire_id is not None:
        where.append("prestataire_id = %s")
        params.append(prestataire_id)
    if assure_id is not None:
        where.append("assure_id = %s")
        params.append(assure_id)
    if statut is not None:
        where.append("statut = %s")
        params.append(statut)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    total = conn.execute(f"SELECT count(*) AS n FROM factures {clause}", params).fetchone()["n"]
    rows = conn.execute(
        "SELECT facture_id, numero_facture, prestataire_id, assure_id, date_soin, nb_lignes, "
        "montant_total, montant_pris_en_charge, reste_a_charge, statut "
        f"FROM factures {clause} ORDER BY date_soin DESC, facture_id DESC LIMIT %s OFFSET %s",
        [*params, limit, offset],
    ).fetchall()
    return rows, total


def lignes_de_factures(conn, facture_ids: list[str]) -> dict[str, list[dict]]:
    if not facture_ids:
        return {}
    rows = conn.execute(
        "SELECT facture_id, num_ligne, code, libelle, quantite, prix_unitaire, montant "
        "FROM lignes_facture WHERE facture_id = ANY(%s) ORDER BY facture_id, num_ligne",
        (facture_ids,),
    ).fetchall()
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["facture_id"], []).append(r)
    return out


# ---------- configuration modifiable (écran d'administration) ----------

def get_configuration(conn, keys: list[str]) -> dict[str, str]:
    try:
        with conn.transaction():
            rows = conn.execute(
                "SELECT cle, valeur FROM configuration WHERE cle = ANY(%s)", (keys,)
            ).fetchall()
    except psycopg.errors.UndefinedTable:
        return {}
    return {r["cle"]: r["valeur"] for r in rows}


def set_configuration(conn, values: dict[str, str]) -> None:
    for cle, valeur in values.items():
        cur = conn.execute("UPDATE configuration SET valeur = %s WHERE cle = %s", (valeur, cle))
        if cur.rowcount == 0:
            conn.execute("INSERT INTO configuration (cle, valeur) VALUES (%s, %s)", (cle, valeur))


# ---------- lecture du journal d'audit ----------

def list_audit(conn, *, event_type: str | None, limit: int) -> list[dict]:
    where, params = "", []
    if event_type:
        where, params = "WHERE j.type_evenement = %s", [event_type]
    return conn.execute(
        "SELECT j.date, j.type_evenement, j.utilisateur_id, u.role AS role_acteur, "
        "j.type_entite, j.entite_id, j.version_modele "
        "FROM journal_audit j LEFT JOIN utilisateurs u ON u.utilisateur_id = j.utilisateur_id "
        f"{where} ORDER BY j.date DESC, j.audit_id DESC LIMIT %s",
        [*params, limit],
    ).fetchall()


# ---------- comptes utilisateurs ----------

_COLS_UTILISATEUR = (
    "utilisateur_id, email, role, assure_id, prestataire_id, actif, derniere_connexion"
)
_CHAMPS_MODIFIABLES = {"role", "assure_id", "prestataire_id", "actif"}


def list_utilisateurs(conn, *, role: str | None = None, actif: bool | None = None,
                      q: str | None = None, limit: int | None = None,
                      offset: int = 0) -> list[dict]:
    where, params = [], []
    if role is not None:
        where.append("role = %s")
        params.append(role)
    if actif is not None:
        where.append("actif = %s")
        params.append(actif)
    if q:
        # les jokers LIKE saisis par l'appelant sont neutralisés
        motif = q.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("lower(email) LIKE %s")
        params.append(f"%{motif}%")
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    pagination = ""
    if limit is not None:
        pagination = " LIMIT %s OFFSET %s"
        params += [limit, offset]
    return conn.execute(
        f"SELECT {_COLS_UTILISATEUR} FROM utilisateurs {clause} "
        f"ORDER BY utilisateur_id{pagination}",
        params,
    ).fetchall()


def get_utilisateur(conn, user_id: int) -> dict | None:
    return conn.execute(
        f"SELECT {_COLS_UTILISATEUR} FROM utilisateurs WHERE utilisateur_id = %s", (user_id,)
    ).fetchone()


def get_utilisateur_par_email(conn, email: str) -> dict | None:
    return conn.execute(
        f"SELECT {_COLS_UTILISATEUR} FROM utilisateurs WHERE email = %s", (email,)
    ).fetchone()


def get_mot_de_passe_hash(conn, user_id: int) -> str | None:
    row = conn.execute(
        "SELECT mot_de_passe_hash FROM utilisateurs WHERE utilisateur_id = %s", (user_id,)
    ).fetchone()
    return row["mot_de_passe_hash"] if row else None


def create_utilisateur(conn, *, email: str, password_hash: str, role: str,
                       assure_id: str | None, prestataire_id: str | None,
                       actif: bool) -> dict | None:
    """Crée un compte ; retourne None si l'adresse existe déjà (aucune erreur levée)."""
    return conn.execute(
        "INSERT INTO utilisateurs (email, mot_de_passe_hash, role, assure_id, prestataire_id, "
        "actif) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (email) DO NOTHING "
        f"RETURNING {_COLS_UTILISATEUR}",
        (email, password_hash, role, assure_id, prestataire_id, actif),
    ).fetchone()


def update_utilisateur(conn, user_id: int, champs: dict) -> dict | None:
    """Met à jour les seuls champs autorisés (noms de colonnes jamais issus du client)."""
    inconnus = set(champs) - _CHAMPS_MODIFIABLES
    if inconnus:
        raise ValueError(f"Champs non modifiables : {sorted(inconnus)}")
    if not champs:
        return get_utilisateur(conn, user_id)
    sets = ", ".join(f"{k} = %s" for k in champs)
    return conn.execute(
        f"UPDATE utilisateurs SET {sets} WHERE utilisateur_id = %s RETURNING {_COLS_UTILISATEUR}",
        [*champs.values(), user_id],
    ).fetchone()


def set_mot_de_passe(conn, user_id: int, password_hash: str) -> None:
    """Change le mot de passe et lève un éventuel verrouillage de connexion."""
    conn.execute(
        "UPDATE utilisateurs SET mot_de_passe_hash = %s, tentatives_echouees = 0, "
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
            "utilisateur_id INTEGER NOT NULL REFERENCES utilisateurs(utilisateur_id) "
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
    return row["utilisateur_id"] if row else None


def invalider_jetons_reinitialisation(conn, user_id: int) -> None:
    ensure_reset_table(conn)
    conn.execute(
        "UPDATE reinitialisations_mdp SET utilise_le = now() "
        "WHERE utilisateur_id = %s AND utilise_le IS NULL",
        (user_id,),
    )


def historique_prestataire(conn, prestataire_id: str, hors_facture_id: str,
                           limit: int = 10) -> list[dict]:
    """Dernières décisions prises sur les AUTRES alertes du même prestataire."""
    return conn.execute(
        "SELECT p.facture_id, p.score, d.decision, d.date_decision, d.gestionnaire_id "
        "FROM decisions_gestionnaire d "
        "JOIN predictions p ON p.prediction_id = d.prediction_id "
        "JOIN factures f ON f.facture_id = p.facture_id "
        "WHERE f.prestataire_id = %s AND p.facture_id <> %s "
        "ORDER BY d.date_decision DESC, d.decision_id DESC LIMIT %s",
        (prestataire_id, hors_facture_id, limit),
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