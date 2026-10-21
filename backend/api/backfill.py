"""Score existing, unscored invoices for a bounded historical period."""
from __future__ import annotations

import argparse
import logging
import os
from collections import Counter
from datetime import date, time
from time import perf_counter

import psycopg
from psycopg.rows import dict_row

from api import repositories as repo
from api.audit import write_audit
from api.config import get_settings
from api.services.calculation_service import calculate_reimbursement
from api.services.context_service import build_context
from api.services.features import build_features_for_invoices
from api.services.fraud_rules_v2 import evaluate_fraud_rules
from api.services.model_registry import get_registry
from api.services.model_types import decision_threshold
from api.services.rules import evaluate_rules
from api.services.scoring import predict_with_explanation
from api.validation import validate_invoice

logger = logging.getLogger(__name__)

_INVOICE_FIELDS = (
    "facture_id", "numero_facture", "prestataire_id", "assure_id", "contrat_id",
    "ordonnance_id", "type_facture", "date_soin", "heure_soin", "date_facture",
    "date_reception", "canal_reception", "mode_reglement", "attestation_pec_id",
    "entente_prealable_id", "devise", "montant_total",
)
_ALERT_RULE_CODES = {
    "QUANTITE_EXCESSIVE", "INCOHERENCE_PROFIL", "DOUBLON",
    "PRESTATAIRE_RADIE", "ORDONNANCE_EXPIREE",
}


def _candidate_ids(conn, days: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT f.facture_id
        FROM factures f
        WHERE f.date_facture >= current_date - (%s * interval '1 day')
          AND f.statut = 'EN_COURS'
          AND NOT EXISTS (
              SELECT 1 FROM predictions p WHERE p.facture_id = f.facture_id
          )
        ORDER BY f.date_facture, f.facture_id
        """,
        (days,),
    ).fetchall()
    return [row["facture_id"] for row in rows]


def _payload_for_invoice(conn, facture_id: str) -> dict:
    invoice = conn.execute(
        f"SELECT {', '.join(_INVOICE_FIELDS)} FROM factures WHERE facture_id = %s",
        (facture_id,),
    ).fetchone()
    if invoice is None:
        raise ValueError("INVOICE_NOT_FOUND")
    payload = {
        key: value.isoformat() if isinstance(value, date) else value
        for key, value in invoice.items()
    }
    if isinstance(invoice["heure_soin"], time):
        payload["heure_soin"] = invoice["heure_soin"].strftime("%H:%M")
    payload["lignes"] = conn.execute(
        """
        SELECT code, type_ligne, quantite, prix_unitaire, montant
        FROM lignes_facture
        WHERE facture_id = %s
        ORDER BY num_ligne
        """,
        (facture_id,),
    ).fetchall()
    return payload


def _score_invoice(conn, facture_id: str, clean: dict, features, admin_id: int,
                   bundle, settings) -> bool:
    started = perf_counter()
    invoice = conn.execute(
        "SELECT statut FROM factures WHERE facture_id = %s FOR UPDATE",
        (facture_id,),
    ).fetchone()
    if invoice is None or invoice["statut"] != "EN_COURS":
        return False
    if conn.execute(
        "SELECT 1 FROM predictions WHERE facture_id = %s",
        (facture_id,),
    ).fetchone():
        return False

    context = build_context(conn, clean)
    calculation = calculate_reimbursement(clean, context)
    fraud_findings = evaluate_fraud_rules(clean, context)
    result = predict_with_explanation(
        bundle, features.loc[[facture_id]], settings.shap_top_k
    )
    threshold = repo.get_seuil_alerte(
        conn, decision_threshold(bundle) or settings.alert_threshold
    )
    score_alert = result["score"] > threshold
    rule_alert_codes = [
        finding.code
        for finding in fraud_findings
        if finding.code in _ALERT_RULE_CODES or finding.severity == "HAUTE"
    ]
    is_alert = score_alert or bool(rule_alert_codes)
    findings = evaluate_rules(conn, clean)

    repo.insert_calculation(conn, facture_id, calculation)
    prediction_id = repo.insert_prediction(
        conn,
        facture_id=facture_id,
        nom_modele=bundle.name,
        version_modele=bundle.version,
        score=result["score"],
        seuil=threshold,
        est_alerte=is_alert,
        latence_ms=int((perf_counter() - started) * 1000),
        variables=result["variables"],
        soumis_par=admin_id,
    )
    repo.insert_shap(conn, prediction_id, facture_id, result["shap_complet"])
    repo.insert_alertes_regles(conn, prediction_id, facture_id, findings)

    if is_alert:
        high_priority_rule = any(
            finding.code in _ALERT_RULE_CODES and finding.severity == "HAUTE"
            for finding in fraud_findings
        )
        repo.insert_alert(
            conn,
            facture_id=facture_id,
            codes=sorted(set(rule_alert_codes or ["SCORE_SUPERIEUR_SEUIL"])),
            priority="HAUTE" if score_alert or high_priority_rule else "MOYENNE",
        )
        conn.execute(
            "UPDATE factures SET statut = 'EN_ATTENTE_GESTIONNAIRE' "
            "WHERE facture_id = %s",
            (facture_id,),
        )

    write_audit(
        conn,
        event_type="prediction",
        actor_id=admin_id,
        entity_type="facture",
        entity_id=facture_id,
        model_name=bundle.name,
        model_version=bundle.version,
        input_data={"facture_id": facture_id, "traitement": "backfill"},
        output_data={
            "prediction_id": prediction_id,
            "score": result["score"],
            "seuil": threshold,
            "is_alert": is_alert,
            "traitement": "backfill",
        },
    )
    return is_alert


def run_backfill(days: int, *, apply: bool) -> dict[str, int]:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    with psycopg.connect(
        database_url, row_factory=dict_row, autocommit=True
    ) as conn:
        candidates = _candidate_ids(conn, days)
        counts = Counter()
        counts["candidates"] = len(candidates)
        if not apply:
            return dict(counts)

        admin = conn.execute(
            """
            SELECT u.utilisateur_id
            FROM utilisateurs u
            JOIN utilisateurs_roles ur ON ur.utilisateur_id = u.utilisateur_id
            JOIN roles r ON r.role_id = ur.role_id
            WHERE r.nom_role = 'administrateur' AND u.est_actif
            ORDER BY u.utilisateur_id
            LIMIT 1
            """
        ).fetchone()
        if admin is None:
            raise RuntimeError("An active administrator account is required for audit")

        bundle = get_registry().ensure_loaded(conn)
        if bundle is None:
            raise RuntimeError("No active model is available for scoring")
        settings = get_settings()

        valid_payloads = []
        clean_by_id = {}
        for facture_id in candidates:
            try:
                errors, clean = validate_invoice(
                    _payload_for_invoice(conn, facture_id), conn
                )
            except Exception as exc:
                code = type(exc).__name__
                logger.exception("backfill_invoice_failed code=%s", code)
                counts["failed"] += 1
                continue
            if errors or clean is None:
                counts["invalid"] += 1
                continue
            valid_payloads.append(clean)
            clean_by_id[facture_id] = clean

        feature_rows = build_features_for_invoices(
            valid_payloads, conn, bundle.feature_names
        )
        for facture_id, clean in clean_by_id.items():
            try:
                with conn.transaction():
                    alert = _score_invoice(
                        conn,
                        facture_id,
                        clean,
                        feature_rows,
                        admin["utilisateur_id"],
                        bundle,
                        settings,
                    )
            except Exception as exc:
                code = type(exc).__name__
                logger.exception("backfill_invoice_failed code=%s", code)
                counts["failed"] += 1
                continue
            counts["scored"] += 1
            counts["alerts"] += int(alert)
        return dict(counts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if args.days < 1:
        parser.error("--days must be at least 1")
    result = run_backfill(args.days, apply=args.apply)
    mode = "applied" if args.apply else "dry-run"
    print(f"Backfill {mode}: {result}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
