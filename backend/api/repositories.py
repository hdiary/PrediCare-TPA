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

def insert_facture(conn, clean: dict, date_reception_defaut: date) -> None:
    """Enregistre une facture reçue par l'API.

    DÉCISION À VALIDER AVEC P1 : les colonnes de décision historique sont NOT NULL dans le
    contrat. Pour une facture neuve : statut EN_COURS, montant_pris_en_charge = 0,
    reste_a_charge = montant_total, montant_eligible = montant_total (pas encore calculé),
    date_traitement NULL. Canal et mode de règlement : valeurs par défaut si absents.
    """
    total = clean["montant_total"]
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
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
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
            "libelle, quantite, prix_unitaire, montant) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
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
