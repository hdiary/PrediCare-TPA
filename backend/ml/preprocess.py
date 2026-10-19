"""Serving adapter that reuses the training feature builder."""
from __future__ import annotations

from datetime import date

import pandas as pd

from ml.features import TABLES, build_features as build_training_features


def _table(conn, name: str) -> pd.DataFrame:
    rows = conn.execute(f"SELECT * FROM {name}").fetchall()
    return pd.DataFrame([dict(row) for row in rows])


def _append_invoice(tables: dict[str, pd.DataFrame], payload: dict) -> None:
    invoice = {
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
        "montant_eligible": payload["montant_total"],
    }
    invoices = tables["factures"]
    tables["factures"] = pd.concat([invoices, pd.DataFrame([invoice])], ignore_index=True)
    lines = [
        {"ligne_id": f"{payload['facture_id']}-L{line['num_ligne']:02d}",
         "facture_id": payload["facture_id"], **line}
        for line in payload["lignes"]
    ]
    tables["lignes_facture"] = pd.concat(
        [tables["lignes_facture"], pd.DataFrame(lines)], ignore_index=True
    )


def build_features(payload: dict, conn) -> pd.DataFrame:
    tables = {name: _table(conn, name) for name in TABLES}
    _append_invoice(tables, payload)
    result = build_training_features(tables)
    return result[0] if isinstance(result, tuple) else result
