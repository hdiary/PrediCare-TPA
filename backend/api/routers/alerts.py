"""Alertes de fraude et décisions du gestionnaire (identifiant d'alerte = facture_id).

Règle métier (CDC) : AUCUNE décision automatique. Le modèle propose (alerte), seul un
gestionnaire décide, et chaque décision est tracée dans le journal d'audit.
"""
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response

from api import repositories as repo
from api.audit import write_audit
from api.db import get_db
from api.deps import require_role
from api.schemas_alerts import AlertSummary, DecisionOut, DecisionRequest, IdentiteOut
from api.services.identity import IdentityUnavailableError, decrypt_identity

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/alerts", tags=["alerts"])
manager_only = Depends(require_role("gestionnaire"))

FactureId = Path(pattern=r"^FAC-\d{8}$", description="Identifiant de la facture")


def _alerte_ou_404(conn, facture_id: str) -> dict:
    pred = repo.get_prediction(conn, facture_id)
    if not pred or not pred["est_alerte"]:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    return pred


@router.get("", response_model=list[AlertSummary], dependencies=[manager_only])
def list_alerts(
    response: Response,
    statut: Literal["en_attente", "traitees", "toutes"] = "en_attente",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    conn=Depends(get_db),
):
    """Liste paginée. Le nombre total (pour la pagination du front) est dans X-Total-Count."""
    response.headers["X-Total-Count"] = str(repo.count_alertes(conn, statut))
    return repo.list_alertes(conn, statut, limit, offset)


@router.get("/{facture_id}", dependencies=[manager_only])
def get_alert(facture_id: str = FactureId, conn=Depends(get_db)):
    pred = _alerte_ou_404(conn, facture_id)
    shap = repo.get_shap(conn, pred["prediction_id"])
    return {
        "prediction": pred,
        "shap": shap["valeurs"] if shap else None,
        "regles": repo.list_alertes_regles(conn, pred["prediction_id"]),
        "decisions": repo.list_decisions(conn, pred["prediction_id"]),
    }


@router.post("/{facture_id}/decision", response_model=DecisionOut, status_code=201)
def decide(
    body: DecisionRequest,
    facture_id: str = FactureId,
    user: dict = Depends(require_role("gestionnaire")),
    conn=Depends(get_db),
):
    pred = repo.get_prediction(conn, facture_id)
    if not pred:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    if not pred["est_alerte"]:
        raise HTTPException(status_code=409, detail="Cette prédiction n'est pas une alerte")

    decision = repo.insert_decision(
        conn,
        prediction_id=pred["prediction_id"],
        facture_id=facture_id,
        gestionnaire_id=user["user_id"],
        decision=body.decision,
        commentaire=body.commentaire,
        montant_economise=body.montant_economise,
    )
    write_audit(
        conn,
        event_type="decision",
        actor_id=user["user_id"],
        entity_type="facture",
        entity_id=facture_id,
        model_name=pred["nom_modele"],
        model_version=pred["version_modele"],   # version du modèle qui a produit l'alerte
        input_data={
            "decision": body.decision,
            "commentaire": body.commentaire,
            "montant_economise": body.montant_economise,
        },
        output_data={
            "decision_id": decision["decision_id"],
            "score": pred["score"],
            "date_decision": decision["date_decision"].isoformat(),
        },
    )
    return decision


@router.get("/{facture_id}/identite", response_model=IdentiteOut)
def identite(
    facture_id: str = FactureId,
    user: dict = Depends(require_role("gestionnaire")),
    conn=Depends(get_db),
):
    """Identité de l'assuré, déchiffrée à la demande pour traiter une alerte. Chaque accès est tracé."""
    _alerte_ou_404(conn, facture_id)
    assure_id = repo.get_assure_de_facture(conn, facture_id)
    blob = repo.get_identite_chiffree(conn, assure_id) if assure_id else None
    if blob is None:
        raise HTTPException(status_code=404, detail="Identité introuvable")
    try:
        data = decrypt_identity(blob)
    except IdentityUnavailableError as exc:
        logger.error("identity_unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="Déchiffrement indisponible") from exc

    write_audit(
        conn,
        event_type="acces_identite",
        actor_id=user["user_id"],
        entity_type="assure",
        entity_id=assure_id,
        input_data={"facture_id": facture_id},
        output_data={"champs": sorted(data)},   # jamais les valeurs
    )
    return IdentiteOut(assure_id=assure_id, **data)
