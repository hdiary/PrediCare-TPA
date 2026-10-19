"""Business-intelligence endpoints backed by the shared five-minute snapshot."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from api.db import get_db
from api.deps import require_role

router = APIRouter(prefix="/bi", tags=["bi"])
_last_kpis: dict[int, dict[str, Any]] = {}
bi_reader = Depends(require_role("gestionnaire", "administrateur"))
logger = logging.getLogger(__name__)


def _rows(conn, query: str, params: tuple[Any, ...] = ()) -> list[dict]:
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def _refresh_state(conn) -> dict[str, Any]:
    row = conn.execute(
        "SELECT last_success_at, last_error FROM bi_refresh_status WHERE singleton"
    ).fetchone()
    if row is None:
        return {"last_success_at": None, "last_error": "Aucun rafraîchissement enregistré"}
    return dict(row)


def _compute_kpis(conn, jours: int) -> dict[str, Any]:
    state = _refresh_state(conn)
    refreshed_at = state["last_success_at"]
    stale = refreshed_at is None or (
        (datetime.now(timezone.utc) - refreshed_at).total_seconds() > 600
    )
    row = conn.execute(
        """
        SELECT
          count(*) FILTER (WHERE score IS NOT NULL) AS factures_traitees,
          count(*) FILTER (WHERE is_alert) AS alertes_generees,
          count(*) FILTER (WHERE is_alert AND decision IS NULL) AS alertes_en_attente,
          count(*) FILTER (WHERE is_alert AND decision IS NOT NULL) AS alertes_traitees,
          count(*) FILTER (WHERE decision IN ('ESCALADER', 'a_investiguer'))
            AS alertes_escaladees,
          coalesce(sum(montant_total), 0) AS montant_reclame,
          coalesce(sum(montant_pris_en_charge), 0) AS montant_rembourse,
          coalesce(sum(montant_total) FILTER (WHERE is_alert), 0) AS montant_a_risque,
          coalesce(sum(montant_reclame - montant_calcule)
            FILTER (WHERE decision IN ('REJETER', 'CONFIRMER_FRAUDE',
                                       'rejete', 'fraude_confirmee')), 0)
            AS montant_economise,
          count(*) FILTER (WHERE decision IN ('CONFIRMER_FRAUDE', 'fraude_confirmee'))
            AS fraudes_confirmees,
          count(*) FILTER (WHERE is_alert AND decision IS NOT NULL) AS alertes_decidees,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY latence_ms)
            FILTER (WHERE latence_ms IS NOT NULL) AS latence_p50_ms,
          percentile_cont(0.95) WITHIN GROUP (ORDER BY latence_ms)
            FILTER (WHERE latence_ms IS NOT NULL) AS latence_p95_ms
        FROM mv_bi_factures
        WHERE date_facture >= current_date - (%s * interval '1 day')
        """,
        (jours,),
    ).fetchone()
    data = dict(row)
    treated = int(data["factures_traitees"] or 0)
    data.update(
        taux_alerte=(int(data["alertes_generees"] or 0) / treated) if treated else None,
        precision_operationnelle=(
            int(data["fraudes_confirmees"] or 0) / int(data["alertes_decidees"])
            if data["alertes_decidees"] else None
        ),
        date_rafraichissement=refreshed_at,
        stale=stale,
        erreur_rafraichissement=state["last_error"] if stale else None,
    )
    data["par_jour"] = _rows(
        conn,
        """
        SELECT date_facture AS jour,
               count(*) FILTER (WHERE score IS NOT NULL) AS factures,
               count(*) FILTER (WHERE is_alert) AS alertes,
               coalesce(sum(montant_reclame - montant_calcule)
                 FILTER (WHERE decision IN ('REJETER', 'CONFIRMER_FRAUDE',
                                            'rejete', 'fraude_confirmee')), 0)
                 AS montant_economise
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
    threshold = conn.execute(
        """
        SELECT threshold
        FROM mv_bi_factures
        WHERE threshold IS NOT NULL
        ORDER BY prediction_id DESC
        LIMIT 1
        """
    ).fetchone()
    data["seuil_alerte"] = threshold["threshold"] if threshold else None
    data["factures_rejetees"] = _rows(
        conn,
        """
        SELECT code, count(*) AS count
        FROM factures_rejetees r
        CROSS JOIN LATERAL jsonb_array_elements_text(r.codes) AS codes(code)
        WHERE r.cree_le >= now() - (%s * interval '1 day')
        GROUP BY code ORDER BY count DESC
        """,
        (jours,),
    )
    data["notifications"] = _rows(
        conn,
        """
        SELECT etat_notification AS etat, count(*) AS count
        FROM alertes
        WHERE cree_le >= now() - (%s * interval '1 day')
        GROUP BY etat_notification ORDER BY etat_notification
        """,
        (jours,),
    )
    data["rag_finops"] = dict(
        conn.execute(
            """
            SELECT coalesce(sum(tokens_in), 0) AS tokens_entree,
                   coalesce(sum(tokens_out), 0) AS tokens_sortie,
                   avg(cache_hit::int) AS taux_cache_hit,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms)
                     AS latence_p50_ms,
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)
                     AS latence_p95_ms
            FROM rag_query_log
            WHERE created_at >= now() - (%s * interval '1 day')
            """,
            (jours,),
        ).fetchone()
    )
    data["rag_finops"]["cout_estime"] = None
    return data


@router.get("/kpis", dependencies=[bi_reader])
def bi_kpis(jours: int = Query(30, ge=1, le=365), conn=Depends(get_db)):
    try:
        with conn.transaction():
            result = _compute_kpis(conn, jours)
        _last_kpis[jours] = result
        return result
    except (psycopg.errors.UndefinedTable, psycopg.errors.UndefinedColumn) as exc:
        logger.exception("BI source unavailable")
        cached = _last_kpis.get(jours)
        if cached is not None:
            return {
                **cached,
                "stale": True,
                "erreur_rafraichissement": "Une source BI est indisponible.",
            }
        raise HTTPException(
            status_code=503,
            detail="Les données BI ne sont pas disponibles et aucune valeur précédente n'existe.",
        ) from exc


@router.get("/model", dependencies=[bi_reader])
def bi_model(conn=Depends(get_db)):
    active = conn.execute(
        """
        SELECT version, metrics, activated_at
        FROM model_versions
        WHERE status = 'ACTIF'
        ORDER BY activated_at DESC NULLS LAST
        LIMIT 1
        """
    ).fetchone()
    metrics = (active["metrics"] or {}).get("test", {}) if active else {}
    return {
        "version_active": active["version"] if active else None,
        "activee_le": active["activated_at"] if active else None,
        "rappel_hors_ligne": metrics.get("recall"),
        "auc_pr": metrics.get("pr_auc"),
        "derive_psi": None,
        "derive_disponible": False,
    }


@router.get("/refresh-status", dependencies=[bi_reader])
def bi_refresh_status(conn=Depends(get_db)):
    state = _refresh_state(conn)
    last_success = state["last_success_at"]
    stale = last_success is None or (
        (datetime.now(timezone.utc) - last_success).total_seconds() > 600
    )
    return {
        "mode": "materialized_views",
        "interval_minutes": 5,
        "last_success_at": last_success,
        "stale": stale,
        "last_error": state["last_error"],
    }
