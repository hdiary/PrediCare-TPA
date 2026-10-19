"""Manager-only fraud alert review and decision routes."""
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response

from api import repositories as repo
from api.audit import write_audit
from api.db import get_db
from api.deps import require_role
from api.schemas_alerts import (
    AlertDetailOut,
    AlertSummary,
    DecisionOut,
    DecisionRequest,
    IdentiteOut,
)
from api.services.identity import IdentityUnavailableError, decrypt_identity

logger = logging.getLogger(__name__)
router = APIRouter(tags=["alerts"])
manager_only = Depends(require_role("gestionnaire"))
FactureId = Path(pattern=r"^FAC-\d{8}$", description="Identifiant de la facture")


def _alerte_ou_404(conn, facture_id: str) -> dict:
    pred = repo.get_prediction(conn, facture_id)
    if not pred or not pred["est_alerte"]:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    return pred


@router.get("/alerts", response_model=list[AlertSummary], dependencies=[manager_only])
@router.get("/alertes", response_model=list[AlertSummary], dependencies=[manager_only])
def list_alerts(
    response: Response,
    statut: Literal[
        "EN_ATTENTE", "VALIDEE", "REJETEE", "ESCALADEE", "TRAITEE", "TOUTES",
        "en_attente", "traitees", "toutes",
    ] = Query("EN_ATTENTE"),
    priorite: Literal["FAIBLE", "MOYENNE", "HAUTE"] | None = None,
    type_alerte: str | None = Query(default=None, alias="type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=200),
    tri: Literal["priorite", "date", "score"] = "priorite",
    conn=Depends(get_db),
):
    """Return manager alerts, ordered by priority by default."""
    if page is not None:
        limit = page_size or limit
        offset = (page - 1) * limit
    response.headers["X-Total-Count"] = str(
        repo.count_alertes(conn, statut, priorite, type_alerte)
    )
    return repo.list_alertes(
        conn, statut, limit, offset, priorite=priorite,
        type_alerte=type_alerte, tri=tri,
    )


@router.get("/alerts/{facture_id}", response_model=AlertDetailOut, dependencies=[manager_only])
@router.get("/alertes/{facture_id}", response_model=AlertDetailOut, dependencies=[manager_only])
def get_alert(facture_id: str = FactureId, conn=Depends(get_db)):
    pred = _alerte_ou_404(conn, facture_id)
    summary = repo.get_alert_summary(conn, facture_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    shap = repo.get_shap(conn, pred["prediction_id"])
    rules = repo.list_alertes_regles(conn, pred["prediction_id"])
    codes = list(summary.get("codes") or [])
    codes.extend(rule["regle_code"] for rule in rules if rule.get("regle_code"))
    return {
        "prediction": summary,
        "facture": repo.get_alert_invoice(conn, facture_id),
        "shap": shap["valeurs"] if shap else None,
        "codes_fraude": sorted(set(codes)),
        "regles": rules,
        "decisions": repo.list_decisions(conn, pred["prediction_id"]),
    }


@router.patch("/alerts/{facture_id}/decision", response_model=DecisionOut)
@router.patch("/alertes/{facture_id}/decision", response_model=DecisionOut)
@router.post("/alerts/{facture_id}/decision", response_model=DecisionOut, status_code=201)
def decide(
    body: DecisionRequest,
    facture_id: str = FactureId,
    user: dict = Depends(require_role("gestionnaire")),
    conn=Depends(get_db),
):
    with conn.transaction():
        pred = repo.get_prediction(conn, facture_id, for_update=True)
        if not pred:
            raise HTTPException(status_code=404, detail="Alerte introuvable")
        if not pred["est_alerte"]:
            raise HTTPException(status_code=409, detail="Cette prédiction n'est pas une alerte")
        if repo.decision_existe(conn, pred["prediction_id"]):
            raise HTTPException(status_code=409, detail="Cette alerte a déjà une décision")

        decision = repo.insert_decision(
            conn,
            prediction_id=pred["prediction_id"],
            facture_id=facture_id,
            gestionnaire_id=user["user_id"],
            decision=body.decision,
            commentaire=body.commentaire,
            montant_economise=body.montant_economise,
        )
        facture_status = {
            "VALIDER": "PAYEE", "valide": "PAYEE",
            "REJETER": "REJETEE", "rejete": "REJETEE",
            "CONFIRMER_FRAUDE": "REJETEE", "fraude_confirmee": "REJETEE",
            "faux_positif": "PAYEE", "ESCALADER": "EN_COURS",
            "a_investiguer": "EN_COURS",
        }[body.decision]
        repo.update_facture_status(conn, facture_id, facture_status)
        write_audit(
            conn,
            event_type="decision",
            actor_id=user["user_id"],
            entity_type="facture",
            entity_id=facture_id,
            model_name=pred["nom_modele"],
            model_version=pred["version_modele"],
            input_data={
                "decision": body.decision,
                "commentaire": body.commentaire,
                "montant_economise": body.montant_economise,
            },
            output_data={
                "decision_id": decision["decision_id"],
                "score": pred["score"],
                "date_decision": decision["date_decision"].isoformat(),
                "statut_facture": facture_status,
            },
        )
    return decision


@router.get("/alerts/{facture_id}/identite", response_model=IdentiteOut)
@router.get("/alertes/{facture_id}/identite", response_model=IdentiteOut)
def identite(
    facture_id: str = FactureId,
    user: dict = Depends(require_role("gestionnaire")),
    conn=Depends(get_db),
):
    """Decrypt insured identity only for a manager and audit the access."""
    _alerte_ou_404(conn, facture_id)
    assure_id = repo.get_assure_de_facture(conn, facture_id)
    blob = repo.get_identite_chiffree(conn, assure_id) if assure_id else None
    if blob is None:
        raise HTTPException(status_code=404, detail="Identité introuvable")
    try:
        data = decrypt_identity(blob)
    except IdentityUnavailableError as exc:
        logger.error("identity_unavailable")
        raise HTTPException(status_code=503, detail="Déchiffrement indisponible") from exc

    write_audit(
        conn,
        event_type="acces_identite",
        actor_id=user["user_id"],
        entity_type="assure",
        entity_id=assure_id,
        input_data={"facture_id": facture_id},
        output_data={"champs": sorted(data)},
    )
    return IdentiteOut(assure_id=assure_id, **data)
