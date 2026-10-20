from datetime import date

from api.services.calculation_service import calculate_reimbursement


def _input(*, soin="2025-02-01", code="ACT-1", total=2000, attestation=None):
    return {
        "date_soin": soin,
        "montant_total": total,
        "attestation_pec_id": attestation,
        "lignes": [
            {
                "code": code,
                "quantite": 1,
                "prix_unitaire": total,
                "montant": total,
            }
        ],
    }


def _context(**overrides):
    context = {
        "guarantee": {
            "taux_remboursement": 50,
            "plafond_annuel_categorie": 1000,
            "franchise_par_facture": 100,
            "delai_carence_jours": 0,
            "plafond_annuel_global": 600,
            "attestation_requise": False,
            "actes_exclus": [],
        },
        "contract": {
            "statut": "ACTIF",
            "date_effet": date(2024, 1, 1),
            "date_fin": None,
            "formule": "CONFORT",
        },
        "insured": {
            "date_adhesion": date(2024, 1, 1),
            "date_radiation": None,
        },
        "references": {},
        "history": {"paid_category": 500, "paid_global": 450},
    }
    context.update(overrides)
    return context


def test_calculation_respects_category_and_global_annual_remaining_limits():
    result = calculate_reimbursement(_input(), _context())

    assert result["montant_calcule"] == 50
    assert result["details"]["plafond_categorie_restant"] == 500
    assert result["details"]["plafond_global_restant"] == 150


def test_calculation_applies_waiting_period_from_later_coverage_start():
    context = _context()
    context["guarantee"]["delai_carence_jours"] = 30
    context["contract"]["date_effet"] = date(2025, 1, 1)
    context["insured"]["date_adhesion"] = date(2025, 1, 10)

    result = calculate_reimbursement(_input(soin="2025-02-08"), context)

    assert result["montant_calcule"] == 0
    assert result["details"]["couverture"] is False


def test_calculation_excludes_noncovered_acts_and_requires_attestation():
    context = _context()
    context["guarantee"]["actes_exclus"] = ["ACT-1"]
    context["guarantee"]["attestation_requise"] = True

    result = calculate_reimbursement(_input(), context)

    assert result["montant_eligible"] == 0
    assert result["montant_calcule"] == 0
    assert result["details"]["actes_exclus"] == ["ACT-1"]
    assert result["details"]["attestation_fournie"] is False
