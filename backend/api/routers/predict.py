"""POST /predict : validation (codes du contrat) -> score + SHAP -> stockage -> audit."""
import logging
import secrets
import time

import psycopg
from fastapi import APIRouter, Body, Depends, HTTPException, File, Form, UploadFile

import json as _json

from api.services.pdf_extract import build_reference, extract_document
from api.repositories import load_reference_tables

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
from api.services.scoring import predict_with_explanation
from api.validation import InvoiceRejected, today_mg, validate_invoice

logger = logging.getLogger(__name__)
router = APIRouter(tags=["predict"])


def _reject(conn, user, raw: dict, erreurs: list[dict], http_status: int, etape: str):
    """Trace le rejet (commit immédiat) puis lève la réponse 422/409/403.

    Aucune valeur reçue n'est journalisée.
    """
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

    # 0. Autorisation : un professionnel de santé ne soumet que les factures de SON prestataire
    #    (sinon il pourrait scorer ou polluer le dossier d'un autre établissement).
    if user["role"] == "professionnel_sante":
        propre = user.get("prestataire_id")
        fourni = payload.get("prestataire_id")
        if propre is None:
            # Compte non rattaché : problème de configuration du compte, pas de la facture.
            _reject(conn, user, payload,
                    [{"code": "PRESTATAIRE_NON_RATTACHE", "champ": "prestataire_id",
                      "message": "Votre compte n'est rattaché à aucun établissement. "
                                 "Contactez un administrateur pour le lier à un prestataire."}],
                    403, "autorisation")
        if fourni is not None and fourni != propre:
            _reject(conn, user, payload,
                    [{"code": "PRESTATAIRE_NON_AUTORISE", "champ": "prestataire_id",
                      "message": "Seules les factures de votre établissement sont acceptées"}],
                    403, "autorisation")

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
    )

# ============================================================================
# NOUVELLE ROUTE : POST /predict/pdf
# Reçoit un PDF, l'extrait via pdf_extract, puis réutilise la route /predict.
# ============================================================================


def _new_facture_id() -> str:
    """Identifiant technique d'une facture déposée (plage FAC-9xxxxxxx, comme le front)."""
    return f"FAC-9{secrets.randbelow(10_000_000):07d}"


def _pdf_to_payload(extracted: dict, prestataire_id: str | None,
                    contrat_id: str | None = None) -> dict:
    """Transforme les champs extraits du PDF en payload accepté par /predict.

    Le PDF ne porte ni `facture_id` (identifiant technique, généré ici) ni `contrat_id`
    (déduit de l'assuré en base) : sans eux /predict rejette la facture (422).
    """
    return {
        "facture_id": _new_facture_id(),
        "numero_facture": extracted.get("numero_facture"),
        "assure_id": extracted.get("assure_id"),
        "contrat_id": extracted.get("contrat_id") or contrat_id,
        "type_facture": extracted.get("type_facture"),
        "date_soin": extracted.get("date_soin"),
        "heure_soin": extracted.get("heure_soin") or "08:00",
        "devise": "MGA",
        "lignes": [
            {
                "code": l["code"],
                "quantite": l["quantite"],
                "prix_unitaire": l["prix_unitaire"],
            }
            for l in extracted.get("lignes", [])
        ],
        **({"prestataire_id": prestataire_id} if prestataire_id else {}),
        **({"ordonnance_id": extracted["ordonnance_id"]}
           if extracted.get("ordonnance_id") else {}),
    }


@router.post(
    "/predict/pdf",
    summary="Scorer une facture à partir d'un PDF",
)
async def predict_pdf(
    file: UploadFile = File(...),
    prescription: str | None = Form(None),
    prestataire_id: str | None = Form(None),
    user: dict = Depends(require_role("professionnel_sante", "gestionnaire")),
    conn=Depends(get_db),
    registry=Depends(get_registry),
):
    # 1. Contrôles basiques
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Seul le format PDF est accepté.")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Le fichier ne doit pas dépasser 10 Mo.")

    # 2. Extraire le PDF
    # load_reference_tables renvoie les tables brutes ; extract_document attend le référentiel
    # construit (codes, nif_to_prestataire, ...) -> build_reference est obligatoire.
    ref = build_reference(load_reference_tables(conn))
    extraction = extract_document(content, ref=ref)

    if not extraction.ok:
        # rejet propre : renvoyer les erreurs d'extraction au front
        raise InvoiceRejected(
            [{"code": "PDF_INVALIDE", "champ": "fichier", "message": e}
             for e in extraction.errors],
            422,
        )

    if extraction.doc_type != "facture":
        raise InvoiceRejected(
            [{"code": "TYPE_INVALIDE", "champ": "fichier",
              "message": f"Document détecté '{extraction.doc_type}', une facture est attendue."}],
            422,
        )

    # 3. Reconstruire le payload
    contrat_id = None
    if extraction.data.get("assure_id") and not extraction.data.get("contrat_id"):
        contrat_id = repo.contrat_de_assure(conn, extraction.data["assure_id"])
    payload = _pdf_to_payload(
        extraction.data, prestataire_id or user.get("prestataire_id"), contrat_id)

    # 4. Si une ordonnance a été fournie côté front, la rattacher
    if prescription:
        try:
            rx = _json.loads(prescription)
            if isinstance(rx, dict) and rx.get("prescription_id"):
                payload["ordonnance_id"] = rx["prescription_id"]
        except _json.JSONDecodeError:
            pass

    # 5. Réutiliser la logique existante
    return predict(payload=payload, user=user, conn=conn, registry=registry)