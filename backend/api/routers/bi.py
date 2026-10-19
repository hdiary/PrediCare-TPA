"""Versioned business-intelligence endpoints for managers and administrators."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import psycopg
from fastapi import APIRouter, Depends, Query

from api.db import get_db
from api.deps import require_role

router = APIRouter(prefix="/bi", tags=["bi"])
_last_kpis: dict[str, Any] | None = None


def _rows(conn, query: str, params: tuple[Any, ...] = ()) -> list[dict]:
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def _compute_kpis(conn, jours: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
          count(*) AS factures_traitees,
          count(*) FILTER (WHERE is_alert) AS alertes_generees,
          count(*) FILTER (WHERE is_alert AND decision IS NULL) AS alertes_en_attente,
          count(*) FILTER (WHERE is_alert AND decision IS NOT NULL) AS alertes_traitees,
          count(*) FILTER (WHERE decision = 'ESCALADER') AS alertes_escaladees,
          coalesce(sum(montant_total), 0) AS montant_reclame,
          coalesce(sum(montant_total) FILTER (WHERE is_alert), 0)
            AS montant_a_risque,
          coalesce(sum(c.montant_reclame - c.montant_calcule)
            FILTER (WHERE decision IN ('REJETER', 'CONFIRMER_FRAUDE',
                                       'rejete', 'fraude_confirmee')), 0)
            AS montant_economise,
          count(*) FILTER (WHERE decision = 'CONFIRMER_FRAUDE') AS fraudes_confirmees,
          count(*) FILTER (WHERE decision IS NOT NULL) AS alertes_decidees,
          count(*) FILTER (WHERE is_alert) AS alertes_pour_taux,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY score)
            FILTER (WHERE score IS NOT NULL) AS score_p50,
          percentile_cont(0.95) WITHIN GROUP (ORDER BY score)
            FILTER (WHERE score IS NOT NULL) AS score_p95
        FROM mv_bi_factures v
        LEFT JOIN calculs_remboursement c ON c.facture_id = v.facture_id
        WHERE v.date_facture >= current_date - (%s * interval '1 day')
        """,
        (jours,),
    ).fetchone()
    data = dict(row)
    decisions = int(data["alertes_decidees"] or 0)
    scorees = int(data["factures_traitees"] or 0)
    data.update(
        taux_alerte=(int(data["alertes_pour_taux"] or 0) / scorees) if scorees else 0,
        precision_operationnelle=(
            int(data["fraudes_confirmees"] or 0) / decisions if decisions else None
        ),
        date_rafraichissement=datetime.now(timezone.utc).isoformat(),
        stale=False,
    )
    data["par_jour"] = _rows(
        conn,
        """
        SELECT date_facture AS jour, count(*) AS factures,
               count(*) FILTER (WHERE is_alert) AS alertes
        FROM mv_bi_factures
        WHERE date_facture >= current_date - (%s * interval '1 day')
        GROUP BY date_facture ORDER BY date_facture
        """,
        (jours,),
    )
    data["top_prestataires"] = _rows(
        conn,
        """
        SELECT prestataire_id, prestataire_nom, count(*) AS alertes
        FROM mv_bi_factures
        WHERE is_alert AND date_facture >= current_date - (%s * interval '1 day')
        GROUP BY prestataire_id, prestataire_nom ORDER BY alertes DESC LIMIT 10
        """,
        (jours,),
    )
    data["distribution_scores"] = _rows(
        conn,
        """
        SELECT width_bucket(score, 0, 1, 10) AS bucket, count(*) AS count
        FROM mv_bi_factures
        WHERE score IS NOT NULL
          AND date_facture >= current_date - (%s * interval '1 day')
        GROUP BY bucket ORDER BY bucket
        """,
        (jours,),
    )
    data["notifications"] = _rows(
        conn,
        """
        SELECT a.etat_notification AS etat, count(*) AS count
        FROM alertes a JOIN factures f USING (facture_id)
        WHERE f.date_facture >= current_date - (%s * interval '1 day')
        GROUP BY a.etat_notification
        """,
        (jours,),
    )
    return data


@router.get("/kpis", dependencies=[Depends(require_role("gestionnaire"))])
def bi_kpis(
    jours: int = Query(30, ge=1, le=365),
    conn=Depends(get_db),
):
    global _last_kpis
    try:
        with conn.transaction():
            result = _compute_kpis(conn, jours)
        _last_kpis = result
        return result
    except (psycopg.errors.UndefinedTable, psycopg.errors.UndefinedColumn):
        if _last_kpis is not None:
            return {**_last_kpis, "stale": True}
        raise


@router.get("/model", dependencies=[Depends(require_role("gestionnaire"))])
def bi_model(conn=Depends(get_db)):
    row = conn.execute(
        """
        SELECT version_modele AS version_active, count(*) AS predictions,
               avg(score) AS score_moyen
        FROM predictions
        GROUP BY version_modele
        ORDER BY max(date) DESC LIMIT 1
        """
    ).fetchone()
    return dict(row) if row else {"version_active": None, "predictions": 0, "score_moyen": None}


@router.get("/refresh-status", dependencies=[Depends(require_role("gestionnaire"))])
def bi_refresh_status():
    return {
        "mode": "materialized_views",
        "interval_minutes": 5,
        "last_known_available": _last_kpis is not None,
    }
