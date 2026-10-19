"""Read repositories for the business schema.

The functions return mappings from psycopg. HTTP layers must validate them with
the Pydantic contracts in ``schemas_domain`` before exposing a response.
"""

from collections.abc import Sequence


def get_provider(conn, prestataire_id: str) -> dict | None:
    return conn.execute(
        "SELECT prestataire_id, nom, type_prestataire, specialite, ville, quartier, "
        "statut, conventionne, jours_ouverture, date_fin_convention FROM prestataires WHERE prestataire_id = %s",
        (prestataire_id,),
    ).fetchone()


def get_insured(conn, assure_id: str) -> dict | None:
    return conn.execute(
        "SELECT assure_id, contrat_id, rang_beneficiaire, sexe, annee_naissance, "
        "ville, date_adhesion, date_radiation FROM assures WHERE assure_id = %s",
        (assure_id,),
    ).fetchone()


def get_contract(conn, contrat_id: str) -> dict | None:
    return conn.execute(
        "SELECT contrat_id, numero_police, formule, date_effet_police, date_effet, "
        "date_fin, statut FROM contrats WHERE contrat_id = %s",
        (contrat_id,),
    ).fetchone()


def get_guarantee(conn, formule: str, categorie: str) -> dict | None:
    return conn.execute(
        "SELECT formule, categorie, taux_remboursement, plafond_annuel_categorie, "
        "franchise_par_facture, delai_carence_jours, plafond_annuel_global, "
        "attestation_requise, actes_exclus, pieces_justificatives FROM garanties "
        "WHERE formule = %s AND categorie = %s",
        (formule, categorie),
    ).fetchone()


def list_reference_codes(conn, codes: Sequence[str] | None = None) -> list[dict]:
    query = (
        "SELECT code, type_ligne, libelle, tarif_min, tarif_reference, tarif_max "
        "FROM ref_codes"
    )
    params: tuple[Sequence[str]] | tuple[()] = ()
    if codes is not None:
        query += " WHERE code = ANY(%s)"
        params = (codes,)
    query += " ORDER BY code"
    return conn.execute(query, params).fetchall()


def get_invoice(conn, facture_id: str) -> dict | None:
    return conn.execute(
        "SELECT facture_id, numero_facture, contrat_id, ordonnance_id, type_facture, "
        "date_soin, heure_soin, date_facture, date_reception, devise, nb_lignes, "
        "montant_total, montant_eligible, montant_pris_en_charge, reste_a_charge, "
        "statut, motif_rejet, date_traitement FROM factures WHERE facture_id = %s",
        (facture_id,),
    ).fetchone()


def get_invoice_for_provider(conn, facture_id: str, prestataire_id: str) -> dict | None:
    return conn.execute(
        "SELECT facture_id, numero_facture, type_facture, date_soin, montant_total, "
        "devise, statut FROM factures WHERE facture_id = %s AND prestataire_id = %s",
        (facture_id, prestataire_id),
    ).fetchone()


def list_invoices_for_insured(conn, assure_id: str, limit: int, offset: int) -> list[dict]:
    return _list_invoices(conn, "assure_id", assure_id, limit, offset)


def list_invoices_for_provider(conn, prestataire_id: str, limit: int, offset: int) -> list[dict]:
    return _list_invoices(conn, "prestataire_id", prestataire_id, limit, offset)


def _list_invoices(conn, column: str, owner_id: str, limit: int, offset: int) -> list[dict]:
    if column not in {"assure_id", "prestataire_id"}:
        raise ValueError("Unsupported invoice owner column")
    return conn.execute(
        "SELECT facture_id, numero_facture, contrat_id, ordonnance_id, type_facture, "
        "date_soin, heure_soin, date_facture, date_reception, devise, nb_lignes, "
        "montant_total, montant_eligible, montant_pris_en_charge, reste_a_charge, "
        "statut, motif_rejet, date_traitement FROM factures "
        f"WHERE {column} = %s ORDER BY date_reception DESC, facture_id DESC "
        "LIMIT %s OFFSET %s",
        (owner_id, limit, offset),
    ).fetchall()
