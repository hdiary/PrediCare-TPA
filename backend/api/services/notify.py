"""Deliver fraud alerts to n8n without making invoice scoring fail."""
import logging
import time

import httpx

from api import repositories as repo
from api.audit import write_audit
from api.config import get_settings

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 3


def _send_notification(
    conn, user: dict, prediction: dict, shap_top: list, codes_fraude: list[str],
    regles: list,
) -> bool:
    """Send an alert with bounded retries; return false for every delivery failure."""
    settings = get_settings()
    facture_id = prediction.get("facture_id")
    payload = {
        "prediction_id": prediction.get("prediction_id"),
        "facture_id": facture_id,
        "assure_id": prediction.get("assure_id"),
        "prestataire_id": prediction.get("prestataire_id"),
        "score": prediction.get("score"),
        "seuil": prediction.get("seuil"),
        "version_modele": prediction.get("version_modele"),
        "montant_total": prediction.get("montant_total"),
        "shap": shap_top[:5],
        "codes_fraude": codes_fraude,
        "regles": [rule.as_dict() if hasattr(rule, "as_dict") else rule for rule in regles],
    }
    if not (settings.n8n_webhook_url and settings.n8n_webhook_secret):
        _record_attempt(conn, user, prediction, 0, False, "configuration_absente")
        _set_notification_state(conn, facture_id, "ECHEC", 0)
        return False

    for attempt in range(1, MAX_ATTEMPTS + 1):
        status_code = None
        try:
            response = httpx.post(
                settings.n8n_webhook_url,
                json=payload,
                headers={"X-Webhook-Secret": settings.n8n_webhook_secret},
                timeout=settings.n8n_timeout_s,
            )
            status_code = response.status_code
            ok = status_code in (200, 202)
        except Exception:
            ok = False

        _record_attempt(conn, user, prediction, attempt, ok, status_code)
        _set_notification_state(conn, facture_id, "ENVOYEE" if ok else "ECHEC", attempt)
        if ok:
            return True
        if attempt < MAX_ATTEMPTS:
            time.sleep(0.2 * attempt)
    return False


def notification_service(
    conn, user: dict, prediction: dict, shap_top: list, codes_fraude: list[str],
    regles: list,
) -> bool:
    """Never propagate notification errors to the invoice API caller."""
    try:
        return _send_notification(conn, user, prediction, shap_top, codes_fraude, regles)
    except Exception:
        logger.warning("Notification n8n en échec")
        _record_attempt(conn, user, prediction, 0, False, "erreur_interne")
        _set_notification_state(conn, prediction.get("facture_id"), "ECHEC", 0)
        return False


def _record_attempt(conn, user, prediction, attempt: int, ok: bool, result) -> None:
    try:
        write_audit(
            conn,
            event_type="notification_n8n_tentative",
            actor_id=user.get("user_id"),
            entity_type="facture",
            entity_id=prediction.get("facture_id"),
            model_name=prediction.get("nom_modele"),
            model_version=prediction.get("version_modele"),
            input_data={"tentative": attempt},
            output_data={"reussie": ok, "resultat": result},
        )
    except Exception:
        logger.warning("Échec de journalisation d'une tentative de notification")


def _set_notification_state(conn, facture_id: str | None, state: str, attempts: int) -> None:
    if not facture_id:
        return
    try:
        repo.update_alert_notification(conn, facture_id, state, attempts)
    except Exception:
        logger.warning("Échec de mise à jour de l'état de notification")


def send_alert(conn, user, prediction: dict, shap_top: list, regles: list) -> bool:
    """Backward-compatible wrapper for existing callers."""
    return notification_service(
        conn, user, prediction, shap_top, prediction.get("codes_fraude", []), regles
    )
