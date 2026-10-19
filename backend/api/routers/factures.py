"""Provider-scoped invoice read routes."""

from fastapi import APIRouter, Body, Depends, Path, Query

from api import repositories_domain as repo
from api.db import get_db
from api.deps import require_role
from api.schemas_domain import FacturePrestataireOut
from api.schemas_domain import InvoiceCreate
from api.schemas_predict import PredictResponse
from api.routers.predict import predict
from api.services.model_registry import get_registry

router = APIRouter(prefix="/factures", tags=["factures"])
provider_only = Depends(require_role("professionnel_sante"))


@router.post("", response_model=PredictResponse, response_model_exclude_none=True, status_code=201)
def create_invoice(
    body: InvoiceCreate = Body(...),
    user: dict = Depends(require_role("professionnel_sante")),
    conn=Depends(get_db),
    registry=Depends(get_registry),
):
    payload = body.model_dump(mode="json")
    if payload.get("prestataire_id") is None:
        payload["prestataire_id"] = user["prestataire_id"]
    return predict(payload=payload, user=user, conn=conn, registry=registry,
                   record_rejection=True, pending_when_unavailable=True)


@router.get("", response_model=list[FacturePrestataireOut], dependencies=[provider_only])
def list_provider_invoices(
    user: dict = Depends(require_role("professionnel_sante")),
    conn=Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List only invoices belonging to the provider in the access token."""
    return repo.list_invoices_for_provider(conn, user["prestataire_id"], limit, offset)


@router.get(
    "/{facture_id}",
    response_model=FacturePrestataireOut,
    dependencies=[provider_only],
)
def get_provider_invoice(
    facture_id: str = Path(pattern=r"^FAC-[0-9]{8}$"),
    user: dict = Depends(require_role("professionnel_sante")),
    conn=Depends(get_db),
):
    row = repo.get_invoice_for_provider(conn, facture_id, user["prestataire_id"])
    if row is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Facture introuvable")
    return row
