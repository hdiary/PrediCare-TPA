"""Deterministic reimbursement calculation, independent from ML scoring."""
from datetime import date, timedelta


def _as_date(value):
    return date.fromisoformat(value) if isinstance(value, str) else value


def calculate_reimbursement(clean: dict, context: dict) -> dict:
    guarantee = context["guarantee"]
    contract = context["contract"]
    total = int(clean["montant_total"])
    base = 0
    eligible = 0
    excluded_codes = set(guarantee.get("actes_exclus") or ())
    for line in clean["lignes"]:
        if line["code"] in excluded_codes:
            continue
        reference = context["references"].get(line["code"], {})
        max_tariff = reference.get("tarif_max")
        unit_base = min(line["prix_unitaire"], max_tariff) if max_tariff is not None else line["prix_unitaire"]
        base += unit_base * line["quantite"]
        eligible += min(line["montant"], unit_base * line["quantite"])

    soin = date.fromisoformat(clean["date_soin"])
    covered = contract["statut"] == "ACTIF"
    insured = context.get("insured", {})
    coverage_start = max(
        filter(None, (_as_date(contract.get("date_effet")), _as_date(insured.get("date_adhesion")))),
        default=None,
    )
    coverage_end = _as_date(contract.get("date_fin"))
    insured_end = _as_date(insured.get("date_radiation"))
    if coverage_start and soin < coverage_start + timedelta(
        days=int(guarantee["delai_carence_jours"])
    ):
        covered = False
    if coverage_end and soin > coverage_end:
        covered = False
    if insured_end and soin > insured_end:
        covered = False
    if not covered:
        return {
            "montant_reclame": total,
            "montant_eligible": 0,
            "montant_calcule": 0,
            "montant_rembourse": 0,
            "reste_a_charge": total,
            "details": {
                "couverture": False,
                "delai_carence_jours": guarantee["delai_carence_jours"],
            },
        }

    if guarantee["attestation_requise"] and not clean.get("attestation_pec_id"):
        eligible = 0

    gross = eligible * int(guarantee["taux_remboursement"]) // 100
    franchise = int(guarantee["franchise_par_facture"])
    paid_category = int(context.get("history", {}).get("paid_category", 0))
    paid_global = int(context.get("history", {}).get("paid_global", 0))
    remaining_category = max(
        0, int(guarantee["plafond_annuel_categorie"]) - paid_category
    )
    remaining_global = max(0, int(guarantee["plafond_annuel_global"]) - paid_global)
    reimbursed = max(0, min(gross, remaining_category, remaining_global) - franchise)
    reimbursed = min(reimbursed, total)
    return {
        "montant_reclame": total,
        "montant_eligible": eligible,
        "montant_calcule": reimbursed,
        "montant_rembourse": reimbursed,
        "reste_a_charge": total - reimbursed,
        "details": {
            "base": base,
            "taux_remboursement": guarantee["taux_remboursement"],
            "franchise": franchise,
            "formule": contract["formule"],
            "actes_exclus": sorted(excluded_codes),
            "attestation_requise": guarantee["attestation_requise"],
            "attestation_fournie": bool(clean.get("attestation_pec_id")),
            "plafond_categorie_restant": remaining_category,
            "plafond_global_restant": remaining_global,
            "remboursement_categorie_annee": paid_category,
            "remboursement_global_annee": paid_global,
        },
    }
