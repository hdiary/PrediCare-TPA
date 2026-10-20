"""Validation des factures : un test par code du contrat de données (section 9.1)."""
from datetime import date

import pytest

from api import validation

TODAY = date(2026, 10, 16)

VALID = {
    "facture_id": "FAC-00000001",
    "numero_facture": "PRE214/2026/00001",
    "prestataire_id": "PRE-00214",
    "assure_id": "ASS-9CAA1484E0",
    "contrat_id": "CTR-000001",
    "type_facture": "CONSULTATION",
    "date_soin": "2026-10-10",
    "heure_soin": "09:30",
    "devise": "MGA",
    "lignes": [{"code": "CONS-GEN", "type_ligne": "ACTE", "quantite": 2, "prix_unitaire": 25000}],
    "montant_total": 50000,
}


def fresh():
    payload = dict(VALID)
    payload["lignes"] = [dict(VALID["lignes"][0])]
    return payload


def codes(raw):
    errors, _ = validation.validate_structure(raw, today=TODAY)
    return {e["code"] for e in errors}


def test_valid_invoice_has_no_error():
    errors, parsed = validation.validate_structure(fresh(), today=TODAY)
    assert errors == []
    assert parsed["montant_total"] == 50000
    assert parsed["lignes"][0]["montant"] == 50000


@pytest.mark.parametrize(
    "mutation,expected",
    [
        (lambda p: p["lignes"][0].update(prix_unitaire=-5), "MONTANT_NEGATIF"),
        (lambda p: p["lignes"][0].update(quantite=0), "MONTANT_NEGATIF"),
        (lambda p: p.update(date_soin="2999-01-01"), "DATE_FUTURE"),
        (lambda p: p.update(date_soin="2026-02-31"), "DATE_IMPOSSIBLE"),
        (lambda p: p.update(date_soin="31/02/2026"), "DATE_IMPOSSIBLE"),
        (lambda p: p.update(heure_soin="25:99"), "DATE_IMPOSSIBLE"),
        (lambda p: p.pop("assure_id"), "CHAMP_OBLIGATOIRE_MANQUANT"),
        (lambda p: p.update(prestataire_id=""), "CHAMP_OBLIGATOIRE_MANQUANT"),
        (lambda p: p.update(montant_total=99999), "TOTAL_INCOHERENT"),
        (lambda p: p["lignes"][0].update(montant=1), "TOTAL_INCOHERENT"),
        (lambda p: p.update(devise="EUR"), "DEVISE_INVALIDE"),
        (lambda p: p.update(lignes=[]), "FACTURE_SANS_LIGNE"),
        (lambda p: p.pop("lignes"), "FACTURE_SANS_LIGNE"),
        (lambda p: p.update(assure_id="ASS-123"), "ASSURE_INCONNU"),
        (lambda p: p.update(prestataire_id="PRE-1"), "PRESTATAIRE_INCONNU"),
        (lambda p: p.update(statut="PAYEE"), "CHAMP_INTERDIT"),
        (lambda p: p.update(montant_pris_en_charge=1000), "CHAMP_INTERDIT"),
        (lambda p: p.update(facture_id="n'importe quoi;--"), "VALEUR_INVALIDE"),
        (lambda p: p["lignes"][0].update(prix_unitaire=10.5), "VALEUR_INVALIDE"),
        (lambda p: p["lignes"][0].update(prix_unitaire="abc"), "VALEUR_INVALIDE"),
        (lambda p: p["lignes"][0].update(prix_unitaire=float("nan")), "VALEUR_INVALIDE"),
        (lambda p: p.update(canal_reception="FAX"), "VALEUR_INVALIDE"),
    ],
)
def test_each_rule_returns_its_code(mutation, expected):
    payload = fresh()
    mutation(payload)
    assert expected in codes(payload)


def test_several_errors_are_all_reported():
    payload = fresh()
    payload.update(devise="EUR", date_soin="2999-01-01")
    payload["lignes"][0]["prix_unitaire"] = -1
    assert {"DEVISE_INVALIDE", "DATE_FUTURE", "MONTANT_NEGATIF"} <= codes(payload)


def test_numero_facture_is_never_used_for_deduplication():
    # un numero_facture déjà vu n'est pas un motif de rejet (signal de fraude, pas une erreur)
    import inspect

    assert "numero_facture" not in inspect.getsource(validation._db_checks)
