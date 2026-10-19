"""Compare serving and training features for a random 1,000-row DB sample."""
import os
import random

import numpy as np
import pandas as pd
import psycopg
from psycopg.rows import dict_row

from ml.features import TABLES, build_features as train_build
from ml.preprocess import build_features_from_tables


def iso(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def main():
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        tables = {name: pd.DataFrame([dict(row) for row in conn.execute(f"SELECT * FROM {name}")]) for name in TABLES}
    full_x, _ = train_build(tables)
    ids = random.Random(20261019).sample(list(full_x.index), min(1000, len(full_x)))
    mismatches = []
    facture_id = ids[0]
    row = tables["factures"].loc[tables["factures"]["facture_id"] == facture_id].iloc[0].to_dict()
    lines = tables["lignes_facture"].loc[
        tables["lignes_facture"]["facture_id"] == facture_id
    ].sort_values("num_ligne").to_dict("records")
    payload = {key: iso(value) for key, value in row.items() if key in {
            "facture_id", "numero_facture", "prestataire_id", "assure_id", "contrat_id",
            "ordonnance_id", "type_facture", "date_soin", "heure_soin", "date_facture",
            "date_reception", "canal_reception", "mode_reglement", "attestation_pec_id",
            "entente_prealable_id", "devise", "montant_total", "montant_eligible",
    }}
    payload["lignes"] = [{key: iso(value) for key, value in line.items()
                               if key in {"num_ligne", "code", "type_ligne", "libelle", "quantite", "prix_unitaire", "montant"}}
                          for line in lines]
    serving = build_features_from_tables(tables, payload).loc[ids]
    expected = full_x.loc[ids]
    for facture_id in ids:
        for column in expected.columns:
            left, right = serving.loc[facture_id, column], expected.loc[facture_id, column]
            if pd.api.types.is_numeric_dtype(expected[column]):
                equal = bool(np.isclose(float(left), float(right), equal_nan=True, rtol=1e-9, atol=1e-9))
            else:
                equal = (str(left) == str(right)) or (pd.isna(left) and pd.isna(right))
            if not equal:
                mismatches.append({"facture_id": facture_id, "feature": column, "api": str(left), "train": str(right)})
                break
    print({"checked": len(ids), "mismatches": len(mismatches), "examples": mismatches[:5]})
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
