"""Envoi de l'alerte au workflow n8n (P3-13) : jamais bloquant, toujours audité."""
import logging
import httpx

from api.audit import write_audit
from api.config import get_settings

logger = logging.getLogger(__name__)


def send_alert(conn, user, prediction: dict, shap_top: list, regles: list) -> bool:
    """POST le webhook n8n si configuré. Retourne True si l'alerte a été transmise."""
    s = get_settings()
    if not (s.n8n_webhook_url and s.n8n_webhook_secret):
        return False
    payload = {
        "prediction_id": prediction["prediction_id"],
        "facture_id": prediction["facture_id"],
        "assure_id": prediction["assure_id"],
        "prestataire_id": prediction["prestataire_id"],
        "score": prediction["score"],
        "version_modele": prediction["version_modele"],
        "montant_total": prediction["montant_total"],
        "shap": shap_top,
        "regles": regles,
    }
    try:
        r = httpx.post(
            s.n8n_webhook_url,
            json=payload,
            headers={"X-Webhook-Secret": s.n8n_webhook_secret},
            timeout=s.n8n_timeout_s,
        )
        ok = r.status_code in (200, 202)
    except Exception as exc:  # n8n down = l'alerte reste en base, pas de 500
        logger.warning("Webhook n8n indisponible: %s", exc)
        ok = False
    write_audit(conn, event_type="alerte", actor_id=user["user_id"],
                entity_type="facture", entity_id=prediction["facture_id"],
                model_name=prediction["nom_modele"],
                model_version=prediction["version_modele"],
                input_data={"score": prediction["score"]},
                output_data={"transmise": ok})
    return ok