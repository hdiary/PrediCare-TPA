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


def list_invoices(
    conn,
    *,
    prestataire_id: str | None,
    assure_id: str | None,
    statut: str | None,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    filters = []
    qualified_filters = []
    params = []
    if prestataire_id is not None:
        filters.append("prestataire_id = %s")
        qualified_filters.append("f.prestataire_id = %s")
        params.append(prestataire_id)
    if assure_id is not None:
        filters.append("assure_id = %s")
        qualified_filters.append("f.assure_id = %s")
        params.append(assure_id)
    if statut is not None:
        filters.append("statut = %s")
        qualified_filters.append("f.statut = %s")
        params.append(statut)

    where = f" WHERE {' AND '.join(filters)}" if filters else ""
    qualified_where = f" WHERE {' AND '.join(qualified_filters)}" if qualified_filters else ""
    total = conn.execute(
        f"SELECT count(*) AS n FROM factures{where}", tuple(params)
    ).fetchone()["n"]
    rows = conn.execute(
        "SELECT f.facture_id, f.numero_facture, f.prestataire_id, p.nom AS prestataire_nom, "
        "f.assure_id, f.date_soin, "
        "f.nb_lignes, f.montant_total, f.montant_pris_en_charge, f.reste_a_charge, f.statut "
        f"FROM factures f LEFT JOIN prestataires p ON p.prestataire_id = f.prestataire_id"
        f"{qualified_where} "
        "ORDER BY f.date_reception DESC, f.facture_id DESC "
        "LIMIT %s OFFSET %s",
        (*params, limit, offset),
    ).fetchall()
    return rows, total


def list_invoices_for_provider(conn, prestataire_id: str, limit: int, offset: int) -> list[dict]:
    return _list_invoices(conn, "prestataire_id", prestataire_id, limit, offset)


def list_invoice_lines(conn, facture_ids: Sequence[str]) -> dict[str, list[dict]]:
    if not facture_ids:
        return {}
    rows = conn.execute(
        "SELECT facture_id, num_ligne, code, libelle, quantite, prix_unitaire, montant "
        "FROM lignes_facture WHERE facture_id = ANY(%s) "
        "ORDER BY facture_id, num_ligne",
        (facture_ids,),
    ).fetchall()
    lines: dict[str, list[dict]] = {}
    for row in rows:
        lines.setdefault(row["facture_id"], []).append(
            {key: row[key] for key in (
                "num_ligne", "code", "libelle", "quantite", "prix_unitaire", "montant"
            )}
        )
    return lines


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
