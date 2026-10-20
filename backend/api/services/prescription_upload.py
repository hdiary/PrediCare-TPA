"""Create an ordonnance record from a scanned prescription PDF."""
import re
from datetime import date
from typing import NoReturn

from api import repositories as repo
from api.services.pdf_extract import extract_document
from api.services.prescription_anomalies import evaluate_prescription
from api.validation import InvoiceRejected

_TYPE_BY_FACTURE = {
    "LABORATOIRE": "EXAMENS",
    "IMAGERIE": "EXAMENS",
    "KINESITHERAPIE": "KINE",
    "OPTIQUE": "OPTIQUE",
}


def _reject(code: str, message: str, status: int = 422) -> NoReturn:
    raise InvoiceRejected(
        [{"code": code, "champ": "ordonnance", "message": message}], status
    )


def _type_ordonnance(conn, codes: list[str], type_facture: str) -> str:
    medication_codes = {
        row["code_medicament"]
        for row in conn.execute("SELECT code_medicament FROM referentiel_medicaments")
    }
    if codes and all(code in medication_codes for code in codes):
        return "MEDICAMENTS"
    if type_facture in _TYPE_BY_FACTURE:
        return _TYPE_BY_FACTURE[type_facture]
    _reject(
        "TYPE_ORDONNANCE_INDETERMINE",
        "Le type d'ordonnance ne peut pas être déduit des actes et de la facture.",
    )


def create_prescription_from_pdf(
    conn,
    content: bytes,
    reference: dict,
    *,
    assure_id: str,
    prescripteur_id: str,
    type_facture: str,
    submitted_by: int,
    expected_id: str | None = None,
    expected_date: str | None = None,
) -> dict:
    extraction = extract_document(content, ref=reference)
    if not extraction.ok or extraction.doc_type != "ordonnance":
        errors = extraction.errors or ["Le document transmis n'est pas une ordonnance."]
        raise InvoiceRejected(
            [
                {
                    "code": "ORDONNANCE_PDF_INVALIDE",
                    "champ": "ordonnance",
                    "message": error,
                }
                for error in errors
            ],
            extraction.http_status if extraction.errors else 422,
        )

    data = extraction.data
    ordonnance_id = data.get("ordonnance_id")
    date_prescription = data.get("date_prescription")
    validite_jours = data.get("validite_jours")
    lignes = data.get("lignes") or []
    if not ordonnance_id or not date_prescription or not validite_jours or not lignes:
        _reject(
            "ORDONNANCE_INCOMPLETE",
            "Les champs requis de l'ordonnance sont illisibles.",
        )
    if not re.fullmatch(r"ORD-\d{7}", ordonnance_id):
        _reject("ORDONNANCE_ID_INVALIDE", "Le numéro d'ordonnance est invalide.")
    if not 1 <= validite_jours <= 32767:
        _reject("ORDONNANCE_VALIDITE_INVALIDE", "La durée de validité est invalide.")
    if type_facture not in {
        "CONSULTATION", "PHARMACIE", "LABORATOIRE", "IMAGERIE", "DENTAIRE",
        "KINESITHERAPIE", "MATERNITE", "OPTIQUE", "HOSPITALISATION",
    }:
        _reject("TYPE_FACTURE_INVALIDE", "Le type de facture est invalide.")
    if expected_id and expected_id != ordonnance_id:
        _reject(
            "ORDONNANCE_ID_INCOHERENT",
            "Le numéro saisi ne correspond pas au PDF.",
        )
    if expected_date and expected_date != date_prescription:
        _reject(
            "ORDONNANCE_DATE_INCOHERENTE",
            "La date saisie ne correspond pas au PDF.",
        )
    if not all(line.get("code") for line in lignes):
        _reject("CODE_ORDONNANCE_INCONNU", "Au moins un code de ligne est absent du référentiel.")
    if any(not 1 <= line["quantite"] <= 32767 for line in lignes):
        _reject("QUANTITE_ORDONNANCE_INVALIDE", "Une quantité de ligne est invalide.")

    codes = [line["code"] for line in lignes]
    if not set(codes) <= reference["codes"]:
        _reject("CODE_ORDONNANCE_INCONNU", "Un code de ligne est absent du référentiel.")
    prescription_type = _type_ordonnance(conn, codes, type_facture)

    if not conn.execute(
        "SELECT 1 FROM assures WHERE assure_id = %s", (assure_id,)
    ).fetchone():
        _reject("ASSURE_INCONNU", "L'assuré associé à la facture est introuvable.")
    if not conn.execute(
        "SELECT 1 FROM prestataires WHERE prestataire_id = %s", (prescripteur_id,)
    ).fetchone():
        _reject("PRESTATAIRE_INCONNU", "Le prestataire associé à la facture est introuvable.")
    if conn.execute(
        "SELECT 1 FROM ordonnances WHERE ordonnance_id = %s", (ordonnance_id,)
    ).fetchone():
        _reject("ORDONNANCE_DEJA_ENREGISTREE", "Cette ordonnance est déjà enregistrée.", 409)

    with conn.transaction():
        conn.execute(
            "INSERT INTO ordonnances (ordonnance_id, assure_id, prescripteur_id, "
            "date_prescription, validite_jours, type_ordonnance, diagnostic, "
            "renseignement_clinique) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                ordonnance_id,
                assure_id,
                prescripteur_id,
                date.fromisoformat(date_prescription),
                validite_jours,
                prescription_type,
                None,
                data.get("renseignement_clinique"),
            ),
        )
        with conn.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO ordonnance_lignes "
                "(ordonnance_id, num_ligne, code, libelle, quantite, posologie) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                [
                    (
                        ordonnance_id,
                        index,
                        line["code"],
                        line["libelle"],
                        line["quantite"],
                        line.get("posologie"),
                    )
                    for index, line in enumerate(lignes, start=1)
                ],
            )
        findings = evaluate_prescription(conn, ordonnance_id)
        repo.insert_prescription_alerts(conn, ordonnance_id, findings, submitted_by)

    return {
        "ordonnance_id": ordonnance_id,
        "anomalies_detectees": len(findings),
        "date_prescription": date_prescription,
        "type_ordonnance": prescription_type,
    }
