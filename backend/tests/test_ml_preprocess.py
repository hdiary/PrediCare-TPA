import pandas as pd
from types import SimpleNamespace

from ml import features, preprocess


def test_table_preserves_columns_when_database_table_is_empty():
    class EmptyCursor:
        description = [SimpleNamespace(name="facture_id"), SimpleNamespace(name="numero_facture")]

        def fetchall(self):
            return []

    class EmptyConnection:
        def execute(self, query):
            assert query == "SELECT * FROM factures"
            return EmptyCursor()

    table = preprocess._table(EmptyConnection(), "factures")

    assert table.empty
    assert table.columns.tolist() == ["facture_id", "numero_facture"]


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
    captured_tables = {}

    def fake_build_features(tables):
        captured_tables.update(tables)
        return feature_rows, pd.DataFrame(index=feature_rows.index)

    monkeypatch.setattr(
        preprocess,
        "build_training_features",
        fake_build_features,
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
    assert pd.api.types.is_numeric_dtype(captured_tables["factures"]["montant_total"])
    assert pd.api.types.is_numeric_dtype(captured_tables["lignes_facture"]["prix_unitaire"])


def test_build_features_for_invoices_returns_every_requested_row(monkeypatch):
    first_id = "FAC-90000001"
    second_id = "FAC-90000002"
    feature_rows = pd.DataFrame(
        {"feature": [1.0, 2.0, 3.0]},
        index=["FAC-HISTORIQUE-1", first_id, second_id],
    )
    monkeypatch.setattr(
        preprocess,
        "build_training_features",
        lambda _tables: (feature_rows, pd.DataFrame(index=feature_rows.index)),
    )
    tables = {name: pd.DataFrame() for name in preprocess.TABLES}
    tables["factures"] = pd.DataFrame(columns=["facture_id"])
    tables["lignes_facture"] = pd.DataFrame(columns=["facture_id"])
    payloads = []
    for invoice_id in (first_id, second_id):
        payloads.append({
            "facture_id": invoice_id,
            "numero_facture": f"INV-{invoice_id}",
            "prestataire_id": "PRE-12345",
            "assure_id": "ASS-1234567890",
            "contrat_id": "CTR-123456",
            "type_facture": "CONSULTATION",
            "date_soin": "2026-10-20",
            "heure_soin": "08:00",
            "devise": "MGA",
            "montant_total": 2500,
            "lignes": [],
        })

    result = preprocess.build_features_for_invoices_from_tables(tables, payloads)

    assert set(result.index) == {first_id, second_id}
