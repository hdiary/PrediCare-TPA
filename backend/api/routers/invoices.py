"""Liste des factures, limitée au périmètre de l'appelant.

- professionnel de santé : les factures de SON prestataire ;
- assuré : SES factures (remboursements) ;
- gestionnaire : toutes les factures.
Le périmètre vient du compte (jeton relu en base), jamais de paramètres de la requête.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from api import repositories_domain as repo
from api.db import get_db
from api.deps import require_role
from api.schemas_invoices import InvoiceList

router = APIRouter(prefix="/invoices", tags=["invoices"])

StatutFacture = Literal["EN_COURS", "PAYEE", "REJETEE"]


@router.get("", response_model=InvoiceList)
def list_invoices(
    statut: StatutFacture | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(require_role("professionnel_sante", "assure", "gestionnaire")),
    conn=Depends(get_db),
):
    prestataire_id = assure_id = None
    if user["role"] == "professionnel_sante":
        prestataire_id = user.get("prestataire_id")
        if prestataire_id is None:
            raise HTTPException(status_code=403, detail="Compte non rattaché à un prestataire")
    elif user["role"] == "assure":
        assure_id = user.get("assure_id")
        if assure_id is None:
            raise HTTPException(status_code=403, detail="Compte non rattaché à un assuré")
    rows, total = repo.list_invoices(
        conn,
        prestataire_id=prestataire_id,
        assure_id=assure_id,
        statut=statut,
        limit=limit,
        offset=offset,
    )
    lignes = repo.list_invoice_lines(conn, [r["facture_id"] for r in rows])
    items = [{**r, "lignes": lignes.get(r["facture_id"], [])} for r in rows]
    return {"items": items, "total": total}
