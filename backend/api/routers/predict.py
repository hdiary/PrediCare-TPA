"""POST /predict : validation (codes du contrat) -> score + SHAP -> stockage -> audit."""
import logging
import time

import psycopg
from fastapi import APIRouter, Body, Depends, HTTPException

from api import repositories as repo
from api.audit import write_audit
from api.config import get_settings
from api.db import get_db
from api.deps import require_role
from api.schemas_predict import PREDICT_OPENAPI_EXTRA, PredictResponse
from api.services.features import (
    FeatureMismatchError,
    FeaturesUnavailableError,
    build_features,
)
from api.services.model_registry import get_registry
from api.services.rules import evaluate_rules
from api.services.scoring import predict_with_explanation
from api.validation import InvoiceRejected, today_mg, validate_invoice

logger = logging.getLogger(__name__)
router = APIRouter(tags=["predict"])


def _reject(conn, user, raw: dict, erreurs: list[dict], http_status: int, etape: str):
    """Trace le rejet (commit immédiat) puis lève la réponse 422/409. Aucune valeur reçue n'est journalisée."""
    facture_id = raw.get("facture_id") if isinstance(raw.get("facture_id"), str) else None
    facture_id = facture_id[:64] if facture_id else None
    write_audit(
        conn,
        event_type="facture_rejetee",
        actor_id=user["user_id"],
        entity_type="facture",
        entity_id=facture_id,
        input_data={"facture_id": facture_id, "etape": etape},
        output_data={"codes": sorted({e["code"] for e in erreurs}), "erreurs": erreurs},
    )
    conn.commit()
    raise InvoiceRejected(erreurs, http_status)


@router.post(
    "/predict",
    response_model=PredictResponse,
    response_model_exclude_none=True,
    summary="Scorer une facture",
    openapi_extra=PREDICT_OPENAPI_EXTRA,
)
def predict(
    payload: dict = Body(...),
    user: dict = Depends(require_role("professionnel_sante", "gestionnaire")),
    conn=Depends(get_db),
    registry=Depends(get_registry),
):
    started = time.perf_counter()
    settings = get_settings()

    # 1. Validation : les 10 codes du contrat (+ CHAMP_INTERDIT, VALEUR_INVALIDE)
    erreurs, clean = validate_invoice(payload, conn)
    if erreurs:
        _reject(conn, user, payload, erreurs, 422, "validation")
    if repo.facture_existe(conn, clean["facture_id"]):
        _reject(conn, user, payload,
                [{"code": "FACTURE_DEJA_ENREGISTREE", "champ": "facture_id",
                  "message": "Cette facture a déjà été scorée"}], 409, "doublon")

    # 2. Modèle actif
    bundle = registry.ensure_loaded()
    if bundle is None:
        raise HTTPException(status_code=503, detail="Modèle indisponible, réessayer plus tard")

    # 3. Variables (même code qu'à l'entraînement) puis score + SHAP
    try:
        features = build_features(clean, conn, bundle.feature_names)
        result = predict_with_explanation(bundle, features, settings.shap_top_k)
    except (FeaturesUnavailableError, FeatureMismatchError) as exc:
        logger.error("feature_error: %s", exc)
        write_audit(conn, event_type="erreur_prediction", actor_id=user["user_id"],
                    entity_type="facture", entity_id=clean["facture_id"],
                    model_name=bundle.name, model_version=bundle.version,
                    input_data={"facture_id": clean["facture_id"]},
                    output_data={"erreur": str(exc)})
        conn.commit()
        raise HTTPException(status_code=500, detail="Erreur de préparation des données") from exc

    seuil = repo.get_seuil_alerte(conn, settings.alert_threshold)
    is_alert = result["score"] >= seuil
    latence_ms = int((time.perf_counter() - started) * 1000)

    # 4. Stockage + audit dans UNE transaction (validée à la sortie de la requête)
    try:
        repo.insert_facture(conn, clean, today_mg())
        prediction_id = repo.insert_prediction(
            conn,
            facture_id=clean["facture_id"],
            nom_modele=bundle.name,
            version_modele=bundle.version,
            score=result["score"],
            seuil=seuil,
            est_alerte=is_alert,
            latence_ms=latence_ms,
            variables=result["variables"],
            soumis_par=user["user_id"],
        )
        repo.insert_shap(conn, prediction_id, clean["facture_id"], result["shap_complet"])
        # Règles de prescription (P3-16) : stockées avec l'explication ; jamais bloquantes
        findings = evaluate_rules(conn, clean)
        repo.insert_alertes_regles(conn, prediction_id, clean["facture_id"], findings)
        write_audit(
            conn,
            event_type="prediction",
            actor_id=user["user_id"],
            entity_type="facture",
            entity_id=clean["facture_id"],
            model_name=bundle.name,
            model_version=bundle.version,
            input_data=clean,
            output_data={
                "prediction_id": prediction_id,
                "score": result["score"],
                "seuil": seuil,
                "is_alert": is_alert,
                "shap": result["shap"],
                "regles": [f.regle_code for f in findings],
                "latence_ms": latence_ms,
            },
        )
    except psycopg.errors.UniqueViolation as exc:   # deux envois simultanés du même facture_id
        raise HTTPException(status_code=409, detail="Facture déjà enregistrée") from exc

    # Un professionnel de santé ne reçoit pas le score (éviter d'aider un fraudeur à l'ajuster)
    if user["role"] == "professionnel_sante":
        return PredictResponse(facture_id=clean["facture_id"], prediction_id=prediction_id)
    return PredictResponse(
        facture_id=clean["facture_id"],
        prediction_id=prediction_id,
        score=result["score"],
        seuil=seuil,
        is_alert=is_alert,
        version_modele=bundle.version,
        shap=result["shap"],
        latence_ms=latence_ms,
        regles=[f.as_dict() for f in findings],
    )
