from api.services.fraud_rules_v2 import (
    rule_acte_fictif,
    rule_doublon,
    rule_fractionnement,
    rule_incoherence_profil,
    rule_lignes_non_prescrites,
    rule_ordonnance_expiree,
    rule_prestataire_radie,
    rule_quantite_excessive,
    rule_soins_jour_ferme,
    rule_substitution_produit,
    rule_surconsommation,
)


def base():
    return {
        "date_soin": "2026-10-19",
        "ordonnance_id": "ORD-0000001",
        "lignes": [{"code": "A", "type_ligne": "ACTE", "quantite": 2}],
    }, {
        "prescription": {"ordonnance_id": "ORD-0000001", "date_prescription": "2026-10-01", "validite_jours": 10},
        "prescription_lines": [{"code": "A", "quantite": 1}],
        "references": {"A": {"ordonnance_requise": False}},
        "provider": {"jours_ouverture": "1234567"},
        "insured": {"sexe": "M", "annee_naissance": 1980},
        "history": {"same_numero": 0, "same_day": 0, "same_ordonnance": 0},
    }


def test_quantite_excessive_positive_and_negative():
    clean, ctx = base()
    assert rule_quantite_excessive(clean, ctx).code == "QUANTITE_EXCESSIVE"
    clean["lignes"][0]["quantite"] = 1
    assert rule_quantite_excessive(clean, ctx) is None


def test_lignes_non_prescrites_positive_and_negative():
    clean, ctx = base()
    clean["lignes"].append({"code": "B", "type_ligne": "ACTE", "quantite": 1})
    assert rule_lignes_non_prescrites(clean, ctx).code == "LIGNES_NON_PRESCRITES"
    clean["lignes"] = [clean["lignes"][0]]
    assert rule_lignes_non_prescrites(clean, ctx) is None


def test_substitution_produit_positive_and_negative():
    clean, ctx = base()
    clean["lignes"] = [{"code": "B", "type_ligne": "MEDICAMENT", "quantite": 1}]
    ctx["references"]["B"] = {"remboursable": False}
    assert rule_substitution_produit(clean, ctx).code == "SUBSTITUTION_PRODUIT"
    ctx["references"]["B"]["remboursable"] = True
    assert rule_substitution_produit(clean, ctx) is None


def test_ordonnance_expiree_positive_and_negative():
    clean, ctx = base()
    assert rule_ordonnance_expiree(clean, ctx).code == "ORDONNANCE_EXPIREE"
    ctx["prescription"]["validite_jours"] = 30
    assert rule_ordonnance_expiree(clean, ctx) is None


def test_soins_jour_ferme_positive_and_negative():
    clean, ctx = base()
    ctx["provider"]["jours_ouverture"] = "234567"
    assert rule_soins_jour_ferme(clean, ctx).code == "SOINS_JOUR_FERME"
    ctx["provider"]["jours_ouverture"] = "1234567"
    assert rule_soins_jour_ferme(clean, ctx) is None


def test_doublon_positive_and_negative():
    clean, ctx = base()
    ctx["history"]["same_numero"] = 1
    assert rule_doublon(clean, ctx).code == "DOUBLON"
    ctx["history"]["same_numero"] = 0
    assert rule_doublon(clean, ctx) is None


def test_fractionnement_positive_and_negative():
    clean, ctx = base()
    ctx["history"]["same_day"] = 1
    assert rule_fractionnement(clean, ctx).code == "FRACTIONNEMENT"
    ctx["history"]["same_day"] = 0
    assert rule_fractionnement(clean, ctx) is None


def test_surconsommation_positive_and_negative():
    clean, ctx = base()
    ctx["history"]["same_ordonnance"] = 1
    assert rule_surconsommation(clean, ctx).code == "SURCONSOMMATION"
    ctx["history"]["same_ordonnance"] = 0
    assert rule_surconsommation(clean, ctx) is None


def test_acte_fictif_positive_and_negative():
    clean, ctx = base()
    clean["ordonnance_id"] = None
    ctx["references"]["A"]["ordonnance_requise"] = True
    assert rule_acte_fictif(clean, ctx).code == "ACTE_FICTIF"
    ctx["references"]["A"]["ordonnance_requise"] = False
    assert rule_acte_fictif(clean, ctx) is None


def test_incoherence_profil_positive_and_negative():
    clean, ctx = base()
    ctx["references"]["A"]["sexe_requis"] = "F"
    assert rule_incoherence_profil(clean, ctx).code == "INCOHERENCE_PROFIL"
    ctx["references"]["A"]["sexe_requis"] = "M"
    assert rule_incoherence_profil(clean, ctx) is None


def test_prestataire_radie_requires_post_dated_end():
    clean, ctx = base()
    ctx["provider"].update({"statut": "RADIE", "date_fin_convention": "2026-10-20"})
    assert rule_prestataire_radie(clean, ctx) is None
    ctx["provider"]["date_fin_convention"] = "2026-10-18"
    assert rule_prestataire_radie(clean, ctx).code == "PRESTATAIRE_RADIE"
import json
from pathlib import Path


def test_model_feature_schema_contains_no_is_flags():
    root = Path(__file__).parents[1]
    schema_path = next(
        candidate for candidate in (
            root / "backend/ml/models_seed/vlightgbm-20261018-1157-078e86/feature_schema.json",
            root / "ml/models_seed/vlightgbm-20261018-1157-078e86/feature_schema.json",
        ) if candidate.exists()
    )
    features = json.loads(schema_path.read_text(encoding="utf-8"))["features"]
    assert not [name for name in features if name.startswith("is_")]
