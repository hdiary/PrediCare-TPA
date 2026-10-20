"""Fraud rules aligned with training feature definitions."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass(frozen=True)
class FraudFinding:
    code: str
    flag: str
    severity: str
    message: str
    details: dict


def _f(code, flag, message, details=None, severity="MOYENNE"):
    return FraudFinding(code, flag, severity, message, details or {})


def _prescribed(ctx):
    return {r["code"]: r for r in ctx.get("prescription_lines", [])}


def _d(value):
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(value) if isinstance(value, str) else value


def rule_quantite_excessive(clean, ctx):
    """is_quantite_excessive: quantity > prescribed quantity * 1.2."""
    for line in clean.get("lignes", []):
        row = _prescribed(ctx).get(line["code"])
        if row and line["quantite"] > float(row["quantite"]) * 1.2:
            return _f("QUANTITE_EXCESSIVE", "is_quantite_excessive", "Quantité facturée excessive", {"code": line["code"]})


def rule_lignes_non_prescrites(clean, ctx):
    """is_lignes_non_prescrites: billed code absent from ordonnance."""
    if ctx.get("prescription") and any(line["code"] not in _prescribed(ctx) for line in clean.get("lignes", [])):
        return _f("LIGNES_NON_PRESCRITES", "is_lignes_non_prescrites", "Ligne absente de l'ordonnance")


def rule_substitution_produit(clean, ctx):
    """is_substitution_produit: different medication and remboursable=false."""
    prescribed = _prescribed(ctx)
    for line in clean.get("lignes", []):
        ref = ctx.get("references", {}).get(line["code"], {})
        if line.get("type_ligne") == "MEDICAMENT" and line["code"] not in prescribed and ref.get("remboursable") is False:
            return _f("SUBSTITUTION_PRODUIT", "is_substitution_produit", "Médicament substitué non remboursable")


def rule_ordonnance_expiree(clean, ctx):
    """is_ordonnance_expiree: date_soin > date_prescription + validite_jours."""
    p = ctx.get("prescription")
    if p and (date.fromisoformat(clean["date_soin"]) - _d(p["date_prescription"])).days > int(p["validite_jours"]):
        return _f("ORDONNANCE_EXPIREE", "is_ordonnance_expiree", "Ordonnance expirée")


def rule_soins_jour_ferme(clean, ctx):
    """is_soins_jour_ferme: weekday not in jours_ouverture."""
    jours = (ctx.get("provider") or {}).get("jours_ouverture")
    if jours and str(date.fromisoformat(clean["date_soin"]).isoweekday()) not in str(jours):
        return _f("SOINS_JOUR_FERME", "is_soins_jour_ferme", "Soin réalisé un jour fermé")


def rule_doublon(clean, ctx):
    """is_doublon: duplicate numero_facture (dup_numero)."""
    if int(ctx.get("history", {}).get("same_numero", 0)) > 0:
        return _f("DOUBLON", "is_doublon", "Numéro de facture déjà utilisé")


def rule_fractionnement(clean, ctx):
    """is_fractionnement: same insured/provider/day group repeated."""
    if int(ctx.get("history", {}).get("same_day", 0)) >= 1:
        return _f("FRACTIONNEMENT", "is_fractionnement", "Factures fractionnées le même jour")


def rule_surconsommation(clean, ctx):
    """is_surconsommation: ordonnance reused by another invoice."""
    if clean.get("ordonnance_id") and int(ctx.get("history", {}).get("same_ordonnance", 0)) > 0:
        return _f("SURCONSOMMATION", "is_surconsommation", "Ordonnance réutilisée")


def rule_acte_fictif(clean, ctx):
    """is_acte_fictif: required ordonnance absent."""
    if not clean.get("ordonnance_id") and any(ctx.get("references", {}).get(l["code"], {}).get("ordonnance_requise") is True for l in clean.get("lignes", [])):
        return _f("ACTE_FICTIF", "is_acte_fictif", "Acte nécessitant une ordonnance", severity="HAUTE")


def rule_incoherence_profil(clean, ctx):
    """is_incoherence_profil: required sex/age incompatible with insured."""
    insured = ctx.get("insured") or {}
    age = date.fromisoformat(clean["date_soin"]).year - int(insured["annee_naissance"]) if insured.get("annee_naissance") else None
    for line in clean.get("lignes", []):
        ref = ctx.get("references", {}).get(line["code"], {})
        if ((ref.get("sexe_requis") and ref["sexe_requis"] != insured.get("sexe")) or (age is not None and ref.get("age_min") is not None and age < ref["age_min"]) or (age is not None and ref.get("age_max") is not None and age > ref["age_max"])):
            return _f("INCOHERENCE_PROFIL", "is_incoherence_profil", "Acte incompatible avec le profil")


def rule_specialite_non_declaree(clean, ctx):
    """is_specialite_non_declaree: grid act specialty differs from provider."""
    specialty = (ctx.get("provider") or {}).get("specialite")
    for line in clean.get("lignes", []):
        ref = ctx.get("references", {}).get(line["code"], {})
        if specialty and line["code"] in ctx.get("tariffs", {}) and ref.get("specialite") not in (None, specialty):
            return _f("SPECIALITE_NON_DECLAREE", "is_specialite_non_declaree", "Spécialité incompatible avec la grille tarifaire")


def rule_surfacturation(clean, ctx):
    """is_surfacturation: prix_unitaire > tarif_max."""
    for line in clean.get("lignes", []):
        maximum = ctx.get("references", {}).get(line["code"], {}).get("tarif_max")
        if maximum is not None and line["prix_unitaire"] > maximum:
            return _f("SURFACTURATION", "is_surfacturation", "Tarif supérieur au référentiel", {"code": line["code"]}, "HAUTE")


def rule_upcoding(clean, ctx):
    """is_upcoding: billed code/type differs from prescribed code/type."""
    prescribed = _prescribed(ctx)
    for line in clean.get("lignes", []):
        row = prescribed.get(line["code"])
        if row and line.get("type_ligne") and row.get("type_ligne") and line["type_ligne"] != row["type_ligne"]:
            return _f("UPCODING", "is_upcoding", "Type de ligne incohérent", {"code": line["code"]})


def rule_prestataire_radie(clean, ctx):
    """is_prestataire_radie: care occurred after a recorded end date."""
    provider = ctx.get("provider") or {}
    if "date_soin" not in clean:
        return
    soin = date.fromisoformat(clean["date_soin"])
    end = provider.get("date_radiation") or provider.get("date_fin_convention")
    if end and soin > _d(end):
        return _f("PRESTATAIRE_RADIE", "is_prestataire_radie", "Prestataire radié", severity="HAUTE")


def rule_hors_couverture(clean, ctx):
    """is_hors_couverture: insured/contract period or waiting period."""
    insured, contract = ctx.get("insured") or {}, ctx.get("contract") or {}
    guarantee = ctx.get("guarantee") or {}
    if "date_soin" not in clean:
        return
    soin = date.fromisoformat(clean["date_soin"])
    start_dates = [
        _d(value) for value in (insured.get("date_adhesion"), contract.get("date_effet"))
        if value
    ]
    start = max(start_dates) if start_dates else None
    end_dates = [
        _d(value) for value in (insured.get("date_radiation"), contract.get("date_fin"))
        if value
    ]
    end = min(end_dates) if end_dates else None
    waiting_days = int(guarantee.get("delai_carence_jours", 0))
    if (
        contract.get("statut") != "ACTIF"
        or (start and soin < start + timedelta(days=waiting_days))
        or (end and soin > end)
    ):
        return _f("HORS_COUVERTURE", "is_hors_couverture", "Soin hors couverture", severity="HAUTE")


RULES = (rule_surfacturation, rule_quantite_excessive, rule_upcoding, rule_lignes_non_prescrites, rule_substitution_produit, rule_ordonnance_expiree, rule_soins_jour_ferme, rule_doublon, rule_fractionnement, rule_surconsommation, rule_acte_fictif, rule_incoherence_profil, rule_prestataire_radie, rule_hors_couverture, rule_specialite_non_declaree)


def evaluate_fraud_rules(clean, context):
    return [finding for rule in RULES if (finding := rule(clean, context))]
