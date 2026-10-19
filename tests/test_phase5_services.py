from api.services.calculation_service import calculate_reimbursement
from api.services.fraud_rules_v2 import evaluate_fraud_rules


def _context():
    return {
        "contract": {"statut": "ACTIF", "formule": "ESSENTIEL"},
        "guarantee": {
            "taux_remboursement": 80,
            "plafond_annuel_categorie": 100000,
            "franchise_par_facture": 1000,
        },
        "references": {"A": {"tarif_max": 1000, "type_ligne": "ACTE"}},
        "provider": {"statut": "ACTIF"},
    }


def test_reimbursement_is_capped_and_deterministic():
    clean = {
        "montant_total": 3000,
        "date_soin": "2026-01-01",
        "lignes": [{"code": "A", "quantite": 3, "prix_unitaire": 1000, "montant": 3000}],
    }
    result = calculate_reimbursement(clean, _context())
    assert result["montant_eligible"] == 3000
    assert result["montant_rembourse"] == 1400
    assert result["reste_a_charge"] == 1600


def test_fraud_rules_are_codes_and_do_not_mutate_input():
    clean = {"montant_total": 1500, "lignes": [{"code": "A", "type_ligne": "ACTE", "prix_unitaire": 1500, "quantite": 1}]}
    findings = evaluate_fraud_rules(clean, _context())
    assert [item.code for item in findings] == ["SURFACTURATION"]
    assert clean["lignes"][0]["prix_unitaire"] == 1500
