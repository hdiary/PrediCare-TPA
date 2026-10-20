import asyncio
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from starlette.datastructures import UploadFile

from api.routers import predict


def _pdf_upload(filename="invoice.pdf"):
    return UploadFile(filename=filename, file=BytesIO(b"%PDF-1.7 test content"))


def test_pdf_route_reuses_prediction_pipeline_with_rejection_and_pending_enabled(monkeypatch):
    extraction = SimpleNamespace(
        ok=True,
        doc_type="facture",
        warnings=["Document lu par OCR : vérifier les champs."],
        data={
            "numero_facture": "INV-1",
            "assure_id": "ASS-1234567890",
            "prestataire_id": "PRE-00214",
            "contrat_id": "CTR-000001",
            "type_facture": "CONSULTATION",
            "date_soin": "2025-02-01",
            "date_facture": "2025-02-02",
            "mode_reglement": "TIERS_PAYANT",
            "devise": "MGA",
            "attestation_pec_id": "APC-000001",
            "lignes": [{"code": "ACT-1", "quantite": 1, "prix_unitaire": 1000}],
        },
    )
    monkeypatch.setattr(predict, "load_reference_tables", lambda _conn: {})
    monkeypatch.setattr(predict, "build_reference", lambda _tables: {})
    monkeypatch.setattr(predict, "extract_document", lambda *_args, **_kwargs: extraction)
    monkeypatch.setattr(predict.repo, "contrat_de_assure", lambda *_args: "CTR-000001")
    audit = MagicMock()
    monkeypatch.setattr(predict, "write_audit", audit)
    recorded = {}

    def fake_predict(**kwargs):
        recorded.update(kwargs)
        return predict.PredictResponse(
            facture_id=kwargs["payload"]["facture_id"],
            prediction_id=None,
        )

    monkeypatch.setattr(predict, "predict", fake_predict)
    response = asyncio.run(
        predict.predict_pdf(
            file=_pdf_upload(),
            prescription=None,
            prescription_scan=None,
            prestataire_id=None,
            user={"user_id": 1, "role": "gestionnaire", "prestataire_id": None},
            conn=MagicMock(),
            registry=MagicMock(),
        )
    )

    assert response.facture_id == recorded["payload"]["facture_id"]
    assert response.avertissements == extraction.warnings
    audit.assert_called_once()
    assert recorded["payload"]["prestataire_id"] == "PRE-00214"
    assert recorded["record_rejection"] is True
    assert recorded["pending_when_unavailable"] is True
    assert recorded["payload"]["date_facture"] == "2025-02-02"
    assert recorded["payload"]["attestation_pec_id"] == "APC-000001"


def test_pdf_extraction_errors_are_audited_and_recorded(monkeypatch):
    extraction = SimpleNamespace(
        ok=False,
        doc_type="facture",
        data={"assure_id": "ASS-1234567890"},
        issues=[{"code": "DATE_FUTURE", "message": "Date de soin future"}],
        http_status=422,
    )
    monkeypatch.setattr(predict, "load_reference_tables", lambda _conn: {})
    monkeypatch.setattr(predict, "build_reference", lambda _tables: {})
    monkeypatch.setattr(predict, "extract_document", lambda *_args, **_kwargs: extraction)
    called = {}

    class Rejected(Exception):
        pass

    def capture_rejection(*args, **kwargs):
        called["args"] = args
        called["kwargs"] = kwargs
        raise Rejected

    monkeypatch.setattr(predict, "_reject", capture_rejection)

    with pytest.raises(Rejected):
        asyncio.run(
            predict.predict_pdf(
                file=_pdf_upload(),
                prescription=None,
                prescription_scan=None,
                prestataire_id=None,
                user={"user_id": 1, "role": "gestionnaire", "prestataire_id": None},
                conn=MagicMock(),
                registry=MagicMock(),
            )
        )

    errors = called["args"][3]
    assert errors == [{
        "code": "DATE_FUTURE",
        "champ": "fichier",
        "message": "Date de soin future",
    }]
    assert called["args"][4:6] == (422, "extraction_pdf")
    assert called["kwargs"]["record_rejection"] is True
