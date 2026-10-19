"""Deterministic reimbursement calculation, independent from ML scoring."""
from datetime import date


def calculate_reimbursement(clean: dict, context: dict) -> dict:
    guarantee = context["guarantee"]
    contract = context["contract"]
    total = int(clean["montant_total"])
    base = 0
    eligible = 0
    for line in clean["lignes"]:
        reference = context["references"].get(line["code"], {})
        max_tariff = reference.get("tarif_max")
        unit_base = min(line["prix_unitaire"], max_tariff) if max_tariff is not None else line["prix_unitaire"]
        base += unit_base * line["quantite"]
        eligible += min(line["montant"], unit_base * line["quantite"])

    soin = date.fromisoformat(clean["date_soin"])
    covered = contract["statut"] == "ACTIF"
    if contract.get("date_effet") and soin < contract["date_effet"]:
        covered = False
    if contract.get("date_fin") and soin > contract["date_fin"]:
        covered = False
    if not covered:
        return {
            "montant_reclame": total,
            "montant_eligible": 0,
            "montant_calcule": 0,
            "montant_rembourse": 0,
            "reste_a_charge": total,
            "details": {"couverture": False},
        }

    gross = eligible * int(guarantee["taux_remboursement"]) // 100
    franchise = int(guarantee["franchise_par_facture"])
    reimbursed = max(0, min(gross, int(guarantee["plafond_annuel_categorie"])) - franchise)
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
        },
    }
