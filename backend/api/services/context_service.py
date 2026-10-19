"""Build the validated business context used by reimbursement and fraud rules."""
from api import repositories_domain as domain


class ContextUnavailableError(Exception):
    """A required business row is missing or cannot be read."""


def build_context(conn, clean: dict) -> dict:
    provider = domain.get_provider(conn, clean["prestataire_id"])
    insured = domain.get_insured(conn, clean["assure_id"])
    contract = domain.get_contract(conn, clean["contrat_id"])
    guarantee = (
        domain.get_guarantee(conn, contract["formule"], clean["type_facture"])
        if contract
        else None
    )
    if not provider or not insured or not contract or not guarantee:
        raise ContextUnavailableError("Contexte facture incomplet")

    codes = [line["code"] for line in clean["lignes"]]
    references = {row["code"]: row for row in domain.list_reference_codes(conn, codes)}
    act_rows = conn.execute(
        "SELECT code_acte AS code, tarif_max, ordonnance_requise, sexe_requis, age_min, age_max, specialite "
        "FROM referentiel_actes WHERE code_acte = ANY(%s)", (codes,)
    ).fetchall()
    med_rows = conn.execute(
        "SELECT code_medicament AS code, prix_reference AS tarif_reference, remboursable "
        "FROM referentiel_medicaments WHERE code_medicament = ANY(%s)", (codes,)
    ).fetchall()
    references.update({row["code"]: {**references.get(row["code"], {}), **row} for row in act_rows})
    references.update({row["code"]: {**references.get(row["code"], {}), **row} for row in med_rows})
    tariffs = conn.execute(
        "SELECT code, tarif_pratique FROM grille_tarifaire "
        "WHERE prestataire_id = %s AND code = ANY(%s)",
        (clean["prestataire_id"], codes),
    ).fetchall()
    tariff_by_code = {row["code"]: row for row in tariffs}
    history = {
        "same_numero": conn.execute(
            "SELECT count(*) AS n FROM factures WHERE numero_facture = %s AND facture_id <> %s",
            (clean["numero_facture"], clean["facture_id"]),
        ).fetchone()["n"],
        "same_day": conn.execute(
            "SELECT count(*) AS n FROM factures WHERE assure_id = %s AND prestataire_id = %s "
            "AND date_soin = %s AND facture_id <> %s",
            (clean["assure_id"], clean["prestataire_id"], clean["date_soin"], clean["facture_id"]),
        ).fetchone()["n"],
        "same_ordonnance": conn.execute(
            "SELECT count(*) AS n FROM factures WHERE ordonnance_id = %s AND facture_id <> %s",
            (clean.get("ordonnance_id"), clean["facture_id"]),
        ).fetchone()["n"] if clean.get("ordonnance_id") else 0,
    }

    prescription = None
    prescription_lines = []
    if clean.get("ordonnance_id"):
        prescription = conn.execute(
            "SELECT ordonnance_id, assure_id, prescripteur_id, date_prescription, "
            "validite_jours, type_ordonnance, diagnostic, renseignement_clinique "
            "FROM ordonnances WHERE ordonnance_id = %s",
            (clean["ordonnance_id"],),
        ).fetchone()
        prescription_lines = conn.execute(
            "SELECT ordonnance_id, num_ligne, code, libelle, quantite, posologie "
            "FROM ordonnance_lignes WHERE ordonnance_id = %s ORDER BY num_ligne",
            (clean["ordonnance_id"],),
        ).fetchall()

    return {
        "provider": provider,
        "insured": insured,
        "contract": contract,
        "guarantee": guarantee,
        "references": references,
        "tariffs": tariff_by_code,
        "prescription": prescription,
        "prescription_lines": prescription_lines,
        "history": history,
    }
