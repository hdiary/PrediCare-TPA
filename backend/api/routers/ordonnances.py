"""Prescription creation and validity checks."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException

from api import repositories as repo
from api.db import get_db
from api.deps import require_role
from api.schemas_domain import PrescriptionCreate, PrescriptionValidityOut
from api.services.prescription_anomalies import evaluate_prescription, load_prescription_context

router = APIRouter(prefix="/ordonnances", tags=["ordonnances"])


@router.post("", status_code=201, response_model=dict)
def create_prescription(
    body: PrescriptionCreate,
    user: dict = Depends(require_role("professionnel_sante")),
    conn=Depends(get_db),
):
    if not user.get("prestataire_id"):
        raise HTTPException(status_code=403, detail="Prestataire absent du JWT")
    if conn.execute("SELECT 1 FROM ordonnances WHERE ordonnance_id = %s", (body.ordonnance_id,)).fetchone():
        raise HTTPException(status_code=409, detail="Ordonnance déjà enregistrée")
    with conn.transaction():
        conn.execute(
            "INSERT INTO ordonnances (ordonnance_id, assure_id, prescripteur_id, date_prescription, "
            "validite_jours, type_ordonnance, diagnostic, renseignement_clinique) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (body.ordonnance_id, body.assure_id, user["prestataire_id"], body.date_prescription,
             body.validite_jours, body.type_ordonnance, body.diagnostic, body.renseignement_clinique),
        )
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO ordonnance_lignes (ordonnance_id, num_ligne, code, libelle, quantite, posologie) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                [(body.ordonnance_id, line.num_ligne, line.code, line.libelle, line.quantite, line.posologie)
                 for line in body.lignes],
            )
        findings = evaluate_prescription(conn, body.ordonnance_id)
        repo.insert_prescription_alerts(conn, body.ordonnance_id, findings, user["user_id"])
    return {"ordonnance_id": body.ordonnance_id, "anomalies_detectees": len(findings)}


@router.get("/{ordonnance_id}/validite", response_model=PrescriptionValidityOut)
def prescription_validity(
    ordonnance_id: str,
    user: dict = Depends(require_role("professionnel_sante", "gestionnaire")),
    conn=Depends(get_db),
):
    try:
        ordonnance, _, _ = load_prescription_context(conn, ordonnance_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Ordonnance introuvable") from exc
    expiration = ordonnance["date_prescription"] + timedelta(days=int(ordonnance["validite_jours"]))
    findings = evaluate_prescription(conn, ordonnance_id)
    date_ok = expiration >= __import__("datetime").date.today()
    # A provider receives only the date validity. Anomaly reasons remain manager-only.
    visible = [finding.code for finding in findings] if user["role"] == "gestionnaire" else []
    return PrescriptionValidityOut(
        ordonnance_id=ordonnance_id,
        valide=date_ok and not findings,
        date_expiration=expiration,
        anomalies=visible,
    )
