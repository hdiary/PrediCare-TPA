"""Reliable delivery of fraud-alert notifications to n8n."""
from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any

MAX_ATTEMPTS = 3


def _payload(alert: Mapping[str, Any]) -> dict[str, Any]:
    """Return the allowlisted notification payload without transport secrets."""
    return {
        "alert_id": alert.get("alert_id"),
        "prediction_id": alert.get("prediction_id"),
        "facture_id": alert.get("facture_id"),
        "assure_id": alert.get("assure_id"),
        "prestataire_id": alert.get("prestataire_id"),
        "score": alert.get("score"),
        "seuil": alert.get("seuil"),
        "version_modele": alert.get("version_modele"),
        "montant_reclame": alert.get("montant_reclame"),
        "montant_calcule": alert.get("montant_calcule"),
        "montant_total": alert.get("montant_total"),
        "shap": list(alert.get("shap") or [])[:5],
        "codes_fraude": list(alert.get("codes_fraude") or []),
        "regles": list(alert.get("regles") or []),
    }


def notify_alert(
    alert: dict,
    *,
    client: Any,
    settings: Any,
    audit: Callable[[dict[str, Any]], None],
) -> str:
    """Send an alert with three bounded attempts and never raise to the caller."""
    url = getattr(settings, "n8n_webhook_url", None)
    secret = getattr(settings, "n8n_webhook_secret", None)
    delay = float(getattr(settings, "n8n_retry_delay_s", 0) or 0)
    if not url or not secret:
        try:
            audit({"attempt": 0, "success": False, "result": "configuration_absente"})
        except Exception:
            pass
        return "FAILED"

    body = _payload(alert)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        success = False
        result: Any = "exception"
        try:
            response = client.post(
                url,
                json=body,
                headers={"X-Webhook-Secret": secret},
                timeout=getattr(settings, "n8n_timeout_s", 3.0),
            )
            status_code = getattr(response, "status_code", None)
            success = status_code in (200, 202)
            result = status_code
        except Exception:
            status_code = None
        try:
            audit({"attempt": attempt, "success": success, "result": result})
        except Exception:
            pass
        if success:
            return "SENT"
        if attempt < MAX_ATTEMPTS and delay:
            time.sleep(delay)
    return "FAILED"
