"""GET /kpis : indicateurs du tableau de bord (agrégats, aucune donnée personnelle)."""
from fastapi import APIRouter, Depends, Query

from api import repositories as repo
from api.db import get_db
from api.deps import require_role
from api.schemas_admin import KpiResponse

router = APIRouter(tags=["kpis"])


@router.get(
    "/kpis",
    response_model=KpiResponse,
    dependencies=[Depends(require_role("administrateur", "gestionnaire"))],
    summary="Indicateurs du tableau de bord",
)
def kpis(
    jours: int = Query(30, ge=1, le=365, description="Fenêtre en jours (30 par défaut)"),
    conn=Depends(get_db),
):
    s = repo.kpi_summary(conn, jours)
    scorees = int(s["factures_scorees"])
    fraudes, faux = int(s["fraudes_confirmees"]), int(s["faux_positifs"])
    return KpiResponse(
        periode_jours=jours,
        factures_scorees=scorees,
        taux_alerte=round(int(s["alertes_total"]) / scorees, 4) if scorees else 0.0,
        alertes_total=int(s["alertes_total"]),
        alertes_en_attente=int(s["alertes_en_attente"]),
        alertes_traitees=int(s["alertes_traitees"]),
        fraudes_confirmees=fraudes,
        faux_positifs=faux,
        a_investiguer=int(s["a_investiguer"]),
        precision=round(fraudes / (fraudes + faux), 4) if (fraudes + faux) else None,
        montant_en_attente=int(s["montant_en_attente"]),
        montant_fraude_confirmee=int(s["montant_fraude_confirmee"]),
        montant_economise=repo.kpi_economies(conn, jours),
        score_moyen=round(float(s["score_moyen"]), 4),
        par_jour=repo.kpi_par_jour(conn, jours),
        regles=repo.kpi_regles(conn, jours),
    )
