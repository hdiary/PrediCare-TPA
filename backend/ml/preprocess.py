"""Serving adapter that reuses the training feature builder."""
from __future__ import annotations

from datetime import date

import pandas as pd

from ml.features import TABLES, build_features as build_training_features


def _table(conn, name: str) -> pd.DataFrame:
    cursor = conn.execute(f"SELECT * FROM {name}")
    rows = cursor.fetchall()
    columns = [column.name for column in cursor.description]
    return pd.DataFrame([dict(row) for row in rows], columns=columns)


def _append_invoices(tables: dict[str, pd.DataFrame], payloads: list[dict]) -> None:
    if not payloads:
        return
    invoice_ids = {payload["facture_id"] for payload in payloads}
    invoices_to_add = [
        {
            "facture_id": payload["facture_id"],
            "numero_facture": payload["numero_facture"],
            "prestataire_id": payload["prestataire_id"],
            "assure_id": payload["assure_id"],
            "contrat_id": payload["contrat_id"],
            "ordonnance_id": payload.get("ordonnance_id"),
            "type_facture": payload["type_facture"],
            "date_soin": payload["date_soin"],
            "heure_soin": payload["heure_soin"],
            "date_facture": payload.get("date_facture", payload["date_soin"]),
            "date_reception": payload.get("date_reception", date.today().isoformat()),
            "canal_reception": payload.get("canal_reception", "PORTAIL_PRESTATAIRE"),
            "mode_reglement": payload.get("mode_reglement", "TIERS_PAYANT"),
            "attestation_pec_id": payload.get("attestation_pec_id"),
            "entente_prealable_id": payload.get("entente_prealable_id"),
            "devise": payload["devise"],
            "nb_lignes": len(payload["lignes"]),
            "montant_total": payload["montant_total"],
            "montant_eligible": payload.get("montant_eligible", payload["montant_total"]),
        }
        for payload in payloads
    ]
    invoices = tables["factures"]
    tables["factures"] = invoices[~invoices["facture_id"].isin(invoice_ids)].copy()
    tables["factures"] = pd.concat(
        [tables["factures"], pd.DataFrame(invoices_to_add)], ignore_index=True
    )
    for column in ("nb_lignes", "montant_total", "montant_eligible"):
        tables["factures"][column] = pd.to_numeric(tables["factures"][column], errors="raise")
    tables["lignes_facture"] = tables["lignes_facture"][
        ~tables["lignes_facture"]["facture_id"].isin(invoice_ids)
    ].copy()
    lines = [
        {
            "ligne_id": f"{payload['facture_id']}-L{line['num_ligne']:02d}",
            "facture_id": payload["facture_id"],
            **line,
        }
        for payload in payloads
        for line in payload["lignes"]
    ]
    tables["lignes_facture"] = pd.concat(
        [tables["lignes_facture"], pd.DataFrame(lines)], ignore_index=True
    )
    for column in ("quantite", "prix_unitaire", "montant"):
        if column in tables["lignes_facture"]:
            tables["lignes_facture"][column] = pd.to_numeric(
                tables["lignes_facture"][column], errors="raise"
            )


def build_features_from_tables(tables: dict[str, pd.DataFrame], payload: dict) -> pd.DataFrame:
    """Build one serving row from a snapshot, using the training implementation."""
    return build_features_for_invoices_from_tables(tables, [payload]).loc[
        lambda features: features.index == payload["facture_id"]
    ]


def build_features_for_invoices_from_tables(
    tables: dict[str, pd.DataFrame], payloads: list[dict]
) -> pd.DataFrame:
    """Build serving rows for several invoices from one consistent table snapshot."""
    snapshot = {name: frame.copy() for name, frame in tables.items()}
    _append_invoices(snapshot, payloads)
    result = build_training_features(snapshot)
    features = result[0] if isinstance(result, tuple) else result
    invoice_ids = {payload["facture_id"] for payload in payloads}
    return features.loc[features.index.isin(invoice_ids)]


def build_features(payload: dict, conn) -> pd.DataFrame:
    tables = {name: _table(conn, name) for name in TABLES}
    return build_features_from_tables(tables, payload)


def build_features_for_invoices(payloads: list[dict], conn) -> pd.DataFrame:
    tables = {name: _table(conn, name) for name in TABLES}
    return build_features_for_invoices_from_tables(tables, payloads)
