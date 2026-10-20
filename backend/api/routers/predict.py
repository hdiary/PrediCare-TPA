"""POST /predict : validation (codes du contrat) -> score + SHAP -> stockage -> audit."""
import logging
import secrets
import time

import httpx
import psycopg
from fastapi import APIRouter, Body, Depends, HTTPException, File, Form, UploadFile

import json as _json

from api.services.pdf_extract import build_reference, extract_document
from api.services.prescription_upload import create_prescription_from_pdf
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
from api.services.calculation_service import calculate_reimbursement
from api.services.context_service import ContextUnavailableError, build_context
from api.services.fraud_rules_v2 import evaluate_fraud_rules
from api.services.model_registry import get_registry
from api.services.notification_service import notify_alert
from api.services.rules import evaluate_rules
from api.services.scoring import predict_with_explanation
from api.validation import InvoiceRejected, today_mg, validate_invoice

logger = logging.getLogger(__name__)
router = APIRouter(tags=["predict"])


def _reject(
    conn,
    user,
    raw: dict,
    erreurs: list[dict],
    http_status: int,
    etape: str,
    record_rejection: bool = False,
):
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
    if record_rejection:
        try:
            repo.insert_rejected_invoice(conn, raw, erreurs, user["user_id"])
        except psycopg.errors.UndefinedTable:
            logger.warning("table factures_rejetees indisponible")
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
    record_rejection: bool = False,
    pending_when_unavailable: bool = False,
):
    started = time.perf_counter()
    settings = get_settings()

    payload = dict(payload)
    if user["role"] == "professionnel_sante":
        propre = user.get("prestataire_id")
        if propre is None:
            _reject(
                conn,
                user,
                payload,
                [{
                    "code": "PRESTATAIRE_NON_RATTACHE",
                    "champ": "prestataire_id",
                    "message": (
                        "Votre compte n'est rattaché à aucun établissement. "
                        "Contactez un administrateur pour le lier à un prestataire."
                    ),
                }],
                403,
                "autorisation",
            )
        supplied = payload.get("prestataire_id")
        if supplied is not None and supplied != propre:
            _reject(
                conn,
                user,
                payload,
                [{
                    "code": "PRESTATAIRE_NON_AUTORISE",
                    "champ": "prestataire_id",
                    "message": "Seules les factures de votre établissement sont acceptées",
                }],
                403,
                "autorisation",
            )
        payload["prestataire_id"] = user["prestataire_id"]

    # 1. Validation : les 10 codes du contrat (+ CHAMP_INTERDIT, VALEUR_INVALIDE)
    erreurs, clean = validate_invoice(payload, conn)
    if erreurs:
        _reject(conn, user, payload, erreurs, 422, "validation", record_rejection)
    if repo.facture_existe(conn, clean["facture_id"]):
        _reject(conn, user, payload,
                [{"code": "FACTURE_DEJA_ENREGISTREE", "champ": "facture_id",
                  "message": "Cette facture a déjà été scorée"}], 409, "doublon")
    if clean.get("ordonnance_id") and not conn.execute(
        "SELECT 1 FROM ordonnances WHERE ordonnance_id = %s",
        (clean["ordonnance_id"],),
    ).fetchone():
        _reject(
            conn,
            user,
            payload,
            [{"code": "ORDONNANCE_INCONNUE", "champ": "ordonnance_id",
              "message": "L'ordonnance doit être enregistrée avant le dépôt de la facture."}],
            422,
            "validation",
            record_rejection,
        )

    calculation = None
    fraud_findings = []
    try:
        context = build_context(conn, clean)
        calculation = calculate_reimbursement(clean, context)
        fraud_findings = evaluate_fraud_rules(clean, context)
    except ContextUnavailableError:
        logger.error("contexte métier indisponible pour %s", clean["facture_id"])
        write_audit(
            conn,
            event_type="erreur_contexte_facture",
            actor_id=user["user_id"],
            entity_type="facture",
            entity_id=clean["facture_id"],
            input_data={"facture_id": clean["facture_id"]},
            output_data={"code": "CONTEXTE_INDISPONIBLE"},
        )
        conn.commit()
        raise HTTPException(
            status_code=503,
            detail="Référentiel métier incomplet, dépôt impossible pour le moment.",
        )

    # 2. Modèle actif
    bundle = registry.ensure_loaded()
    if bundle is None:
        if not pending_when_unavailable:
            raise HTTPException(status_code=503, detail="Modèle indisponible, réessayer plus tard")
        try:
            repo.insert_facture(conn, clean, today_mg(), calculation, "EN_ATTENTE_GESTIONNAIRE")
            if calculation is not None:
                repo.insert_calculation(conn, clean["facture_id"], calculation)
            write_audit(
                conn, event_type="prediction_en_attente", actor_id=user["user_id"],
                entity_type="facture", entity_id=clean["facture_id"],
                input_data={"facture_id": clean["facture_id"]},
                output_data={
                    "scoring_indisponible": True,
                    "codes_fraude": [finding.code for finding in fraud_findings],
                    "montant_calcule": calculation.get("montant_calcule") if calculation else None,
                },
            )
            conn.commit()
        except psycopg.errors.UniqueViolation as exc:
            raise HTTPException(status_code=409, detail="Facture déjà enregistrée") from exc
        return PredictResponse(
            accepte=False,
            facture_id=clean["facture_id"],
            transaction_id=clean["facture_id"],
            prediction_id=None,
            montant_calcule=calculation.get("montant_calcule") if calculation else None,
            statut="EN_ATTENTE_GESTIONNAIRE",
            scoring_indisponible=True,
        )

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
    alert_rule_codes = {
        "QUANTITE_EXCESSIVE", "INCOHERENCE_PROFIL", "DOUBLON",
        "PRESTATAIRE_RADIE", "ORDONNANCE_EXPIREE",
    }
    rule_alert_codes = [
        f.code for f in fraud_findings
        if f.code in alert_rule_codes or f.severity == "HAUTE"
    ]
    score_alert = result["score"] > seuil
    is_alert = score_alert or bool(rule_alert_codes)
    latence_ms = int((time.perf_counter() - started) * 1000)
    alerte_id = None

    # 4. Stockage + audit dans UNE transaction (validée à la sortie de la requête)
    try:
        with conn.transaction():
            repo.insert_facture(
                conn,
                clean,
                today_mg(),
                calculation,
                "EN_ATTENTE_GESTIONNAIRE" if is_alert else "EN_COURS",
            )
            if calculation is not None:
                repo.insert_calculation(conn, clean["facture_id"], calculation)
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
            if is_alert:
                high_priority_rule = any(
                    finding.code in rule_alert_codes and finding.severity == "HAUTE"
                    for finding in fraud_findings
                )
                alerte_id = repo.insert_alert(
                    conn,
                    facture_id=clean["facture_id"],
                    codes=sorted(set(rule_alert_codes or ["SCORE_SUPERIEUR_SEUIL"])),
                    priority="HAUTE" if score_alert or high_priority_rule else "MOYENNE",
                )
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
                    "codes_fraude": [f.code for f in fraud_findings],
                    "latence_ms": latence_ms,
                },
            )
    except psycopg.errors.UniqueViolation as exc:   # deux envois simultanés du même facture_id
        raise HTTPException(status_code=409, detail="Facture déjà enregistrée") from exc

    # Un professionnel de santé ne reçoit pas le score (éviter d'aider un fraudeur à l'ajuster)
    if is_alert and alerte_id:
        notification_events = []

        def audit_notification(event: dict) -> None:
            notification_events.append(event)
            write_audit(
                conn,
                event_type="notification_n8n_tentative",
                actor_id=user["user_id"],
                entity_type="facture",
                entity_id=clean["facture_id"],
                model_name=bundle.name,
                model_version=bundle.version,
                input_data={"tentative": event["attempt"]},
                output_data={"reussie": event["success"], "resultat": event["result"]},
            )

        notification_status = notify_alert(
            {
                "alert_id": alerte_id,
                "prediction_id": prediction_id,
                "facture_id": clean["facture_id"],
                "assure_id": clean["assure_id"],
                "prestataire_id": clean["prestataire_id"],
                "score": result["score"],
                "seuil": seuil,
                "version_modele": bundle.version,
                "nom_modele": bundle.name,
                "montant_total": clean["montant_total"],
                "montant_reclame": calculation.get("montant_reclame") if calculation else None,
                "montant_calcule": calculation.get("montant_calcule") if calculation else None,
                "codes_fraude": [finding.code for finding in fraud_findings],
                "shap": result["shap"],
                "regles": [finding.as_dict() for finding in findings],
            },
            client=httpx,
            settings=settings,
            audit=audit_notification,
        )
        repo.update_alert_notification(
            conn, clean["facture_id"], "ENVOYEE" if notification_status == "SENT" else "ECHEC",
            len(notification_events),
        )
        conn.commit()

    if user["role"] == "professionnel_sante":
        return PredictResponse(
            facture_id=clean["facture_id"],
            transaction_id=clean["facture_id"],
            prediction_id=prediction_id,
            montant_calcule=calculation.get("montant_calcule") if calculation else None,
            statut="EN_ATTENTE_GESTIONNAIRE" if is_alert else "EN_COURS",
        )
    return PredictResponse(
        facture_id=clean["facture_id"],
        transaction_id=clean["facture_id"],
        prediction_id=prediction_id,
        montant_calcule=calculation.get("montant_calcule") if calculation else None,
        statut="EN_ATTENTE_GESTIONNAIRE" if is_alert else "EN_COURS",
        score=result["score"],
        seuil=seuil,
        is_alert=is_alert,
        version_modele=bundle.version,
        shap=result["shap"],
        latence_ms=latence_ms,
        regles=[f.as_dict() for f in findings],
        codes_fraude=[f.code for f in fraud_findings],
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
        "date_facture": extracted.get("date_facture"),
        "heure_soin": extracted.get("heure_soin") or "08:00",
        "devise": extracted.get("devise") or "MGA",
        "mode_reglement": extracted.get("mode_reglement"),
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
        **({"attestation_pec_id": extracted["attestation_pec_id"]}
           if extracted.get("attestation_pec_id") else {}),
    }


@router.post(
    "/predict/pdf",
    summary="Scorer une facture à partir d'un PDF",
)
async def predict_pdf(
    file: UploadFile = File(...),
    prescription: str | None = Form(None),
    prescription_scan: UploadFile | None = File(None),
    prestataire_id: str | None = Form(None),
    user: dict = Depends(require_role("professionnel_sante", "gestionnaire")),
    conn=Depends(get_db),
    registry=Depends(get_registry),
):
    # 1. Contrôles basiques
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        _reject(
            conn, user, {"facture_id": _new_facture_id()},
            [{"code": "FORMAT_INVALIDE", "champ": "fichier",
              "message": "Seul le format PDF est accepté."}],
            400, "format_pdf", record_rejection=True,
        )

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        _reject(
            conn, user, {"facture_id": _new_facture_id()},
            [{"code": "FORMAT_INVALIDE", "champ": "fichier",
              "message": "Le fichier ne doit pas dépasser 10 Mo."}],
            400, "format_pdf", record_rejection=True,
        )

    # 2. Extraire le PDF
    # load_reference_tables renvoie les tables brutes ; extract_document attend le référentiel
    # construit (codes, nif_to_prestataire, ...) -> build_reference est obligatoire.
    ref = build_reference(load_reference_tables(conn))
    extraction = extract_document(content, ref=ref)

    if not extraction.ok:
        payload = {
            "facture_id": _new_facture_id(),
            "assure_id": extraction.data.get("assure_id"),
            "prestataire_id": (
                prestataire_id or extraction.data.get("prestataire_id")
                or user.get("prestataire_id")
            ),
        }
        _reject(
            conn, user, payload,
            [{"code": issue["code"], "champ": "fichier", "message": issue["message"]}
             for issue in extraction.issues],
            extraction.http_status, "extraction_pdf", record_rejection=True,
        )

    if extraction.doc_type != "facture":
        _reject(
            conn, user, {"facture_id": _new_facture_id()},
            [{"code": "TYPE_INVALIDE", "champ": "fichier",
              "message": f"Document détecté '{extraction.doc_type}', une facture est attendue."}],
            422, "type_document_pdf", record_rejection=True,
        )

    # 3. Reconstruire le payload
    contrat_id = None
    if extraction.data.get("assure_id") and not extraction.data.get("contrat_id"):
        contrat_id = repo.contrat_de_assure(conn, extraction.data["assure_id"])
    payload = _pdf_to_payload(
        extraction.data,
        prestataire_id or user.get("prestataire_id") or extraction.data.get("prestataire_id"),
        contrat_id,
    )

    # 4. Parse and persist an attached prescription before linking the invoice.
    prescription_data = {}
    if prescription:
        try:
            parsed_prescription = _json.loads(prescription)
        except _json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="Les informations d'ordonnance sont invalides.") from exc
        if not isinstance(parsed_prescription, dict):
            raise HTTPException(status_code=422, detail="Les informations d'ordonnance sont invalides.")
        prescription_data = parsed_prescription

    if prescription_scan:
        if not prescription_scan.filename or not prescription_scan.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Le scan d'ordonnance doit être un PDF.")
        prescription_content = await prescription_scan.read()
        if len(prescription_content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Le scan ne doit pas dépasser 10 Mo.")
        ordonnance = create_prescription_from_pdf(
            conn,
            prescription_content,
            ref,
            assure_id=payload["assure_id"],
            prescripteur_id=payload.get("prestataire_id") or user.get("prestataire_id"),
            type_facture=payload["type_facture"],
            submitted_by=user["user_id"],
            expected_id=prescription_data.get("prescription_id"),
            expected_date=prescription_data.get("prescription_date"),
        )
        payload["ordonnance_id"] = ordonnance["ordonnance_id"]
    elif prescription_data.get("prescription_id"):
        payload["ordonnance_id"] = prescription_data["prescription_id"]

    # 5. Réutiliser la logique existante
    response = predict(
        payload=payload, user=user, conn=conn, registry=registry,
        record_rejection=True, pending_when_unavailable=True,
    )
    if extraction.warnings:
        response.avertissements = extraction.warnings
        write_audit(
            conn,
            event_type="avertissement_extraction_pdf",
            actor_id=user["user_id"],
            entity_type="facture",
            entity_id=payload["facture_id"],
            input_data={"facture_id": payload["facture_id"]},
            output_data={"avertissements": extraction.warnings},
        )
        conn.commit()
    return response