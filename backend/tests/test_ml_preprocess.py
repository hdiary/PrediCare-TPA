import pandas as pd

from ml import features, preprocess


def test_code_reference_keeps_nullable_boolean_flag_numeric():
    tables = {
        "referentiel_actes": pd.DataFrame({
            "code_acte": ["ACT-1"],
            "tarif_min": [10],
            "tarif_reference": [15],
            "tarif_max": [20],
            "sexe_requis": [None],
            "age_min": [None],
            "age_max": [None],
            "ordonnance_requise": [True],
            "specialite": [None],
        }),
        "referentiel_medicaments": pd.DataFrame({
            "code_medicament": ["MED-1"],
            "prix_reference": [5],
            "remboursable": [True],
        }),
    }

    reference = features._build_code_reference(tables)

    assert pd.api.types.is_numeric_dtype(reference["ordonnance_requise"])
    assert reference["ordonnance_requise"].iloc[0] == 1.0
    assert pd.isna(reference["ordonnance_requise"].iloc[1])


def test_build_features_from_tables_returns_only_the_submitted_invoice(monkeypatch):
    facture_id = "FAC-90000001"
    feature_rows = pd.DataFrame(
        {"feature": [1.0, 2.0, 3.0]},
        index=["FAC-HISTORIQUE-1", facture_id, "FAC-HISTORIQUE-2"],
    )
    monkeypatch.setattr(
        preprocess,
        "build_training_features",
        lambda _: (feature_rows, pd.DataFrame(index=feature_rows.index)),
    )
    tables = {name: pd.DataFrame() for name in preprocess.TABLES}
    tables["factures"] = pd.DataFrame(columns=["facture_id"])
    tables["lignes_facture"] = pd.DataFrame(columns=["facture_id"])
    payload = {
        "facture_id": facture_id,
        "numero_facture": "FAC-TEST-1",
        "prestataire_id": "PRE-12345",
        "assure_id": "ASS-1234567890",
        "contrat_id": "CTR-12345",
        "type_facture": "CONSULTATION",
        "date_soin": "2026-10-20",
        "heure_soin": "08:00",
        "devise": "MGA",
        "montant_total": 2500,
        "lignes": [
            {
                "num_ligne": 1,
                "code": "CONS-GEN",
                "type_ligne": "ACTE",
                "libelle": "Consultation",
                "quantite": 1,
                "prix_unitaire": 2500,
                "montant": 2500,
            }
        ],
    }

    result = preprocess.build_features_from_tables(tables, payload)

    assert result.index.tolist() == [facture_id]
    assert result.iloc[0]["feature"] == 2.0
