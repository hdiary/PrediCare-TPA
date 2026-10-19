"""Tests unitaires de prescription_rules (jeux de données minimaux et contrôlés)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import prescription_rules as R  # noqa: E402


def tables(ordos, lignes, presc=None, adhesion="2025-01-01"):
    presc = presc or [dict(prestataire_id="P1", type_prestataire="CABINET_GENERALISTE",
                           specialite=None, statut="ACTIF", numero_onm="ONM-12345",
                           date_fin_convention=None)]
    return {
        "ordonnances": pd.DataFrame(ordos),
        "ordonnance_lignes": pd.DataFrame(lignes),
        "prestataires": pd.DataFrame(presc),
        "assures": pd.DataFrame([dict(assure_id="A1", date_adhesion=adhesion)]),
    }


def ordo(oid, date="2025-06-01", diag="Hypertension artérielle", presc="P1", assure="A1"):
    return dict(ordonnance_id=oid, assure_id=assure, prescripteur_id=presc,
                date_prescription=date, diagnostic=diag, type_ordonnance="MEDICAMENTS")


def ligne(oid, code="MED-X", q=1, poso="1 cp x 2/jour pendant 5 jours"):
    return dict(ordonnance_id=oid, code=code, quantite=q, posologie=poso)


REF = {"diag_code": {("Hypertension artérielle", "MED-X")}, "spec_diag": set(),
       "specs_jugees": set(), "qte_max": {"MED-X": 2}, "duree_max": 7.0}


def regles(t, ref=REF):
    return set(R.check_ordonnances(t, ref)["regle"])


def test_ordonnance_normale_aucune_alerte():
    t = tables([ordo("O1")], [ligne("O1")])
    assert R.check_ordonnances(t, REF).empty


def test_antidatee():
    t = tables([ordo("O1", date="2024-12-01")], [ligne("O1")])
    assert "ORDONNANCE_ANTIDATEE" in regles(t)


def test_prescripteur_radie_apres_fin_convention():
    p = [dict(prestataire_id="P1", type_prestataire="CABINET_GENERALISTE", specialite=None,
              statut="RADIE", numero_onm="ONM-12345", date_fin_convention="2025-03-01")]
    t = tables([ordo("O1", date="2025-06-01")], [ligne("O1")], presc=p)
    assert "PRESCRIPTEUR_RADIE" in regles(t)


def test_prescripteur_radie_avant_fin_convention_ok():
    p = [dict(prestataire_id="P1", type_prestataire="CABINET_GENERALISTE", specialite=None,
              statut="RADIE", numero_onm="ONM-12345", date_fin_convention="2025-12-01")]
    assert R.check_ordonnances(tables([ordo("O1")], [ligne("O1")], presc=p), REF).empty


@pytest.mark.parametrize("onm", [None, "12345", "ONM-1"])
def test_onm_invalide_pour_un_medecin(onm):
    p = [dict(prestataire_id="P1", type_prestataire="CABINET_GENERALISTE", specialite=None,
              statut="ACTIF", numero_onm=onm, date_fin_convention=None)]
    assert "PRESCRIPTEUR_RADIE" in regles(tables([ordo("O1")], [ligne("O1")], presc=p))


def test_prescripteur_inconnu():
    t = tables([ordo("O1", presc="P999")], [ligne("O1")])
    assert "PRESCRIPTEUR_RADIE" in regles(t)


def test_doublon_prescription():
    t = tables([ordo("O1", date="2025-06-01"), ordo("O2", date="2025-06-02")],
               [ligne("O1"), ligne("O2")])
    a = R.check_ordonnances(t, REF)
    assert list(a[a.regle == "DOUBLON_PRESCRIPTION"].ordonnance_id) == ["O2"]  # le renvoi


def test_renouvellement_espace_pas_un_doublon():
    t = tables([ordo("O1", date="2025-06-01"), ordo("O2", date="2025-07-01")],
               [ligne("O1"), ligne("O2")])
    assert "DOUBLON_PRESCRIPTION" not in regles(t)


def test_inadequation_diagnostic():
    t = tables([ordo("O1", diag="Asthme")], [ligne("O1")])
    assert "INADEQUATION_DIAGNOSTIC" in regles(t)


def test_diagnostic_absent_pas_juge():
    t = tables([ordo("O1", diag=None)], [ligne("O1")])
    assert "INADEQUATION_DIAGNOSTIC" not in regles(t)


def test_quantite_surchargee():
    t = tables([ordo("O1")], [ligne("O1", q=9)])
    assert "ORDONNANCE_FALSIFIEE" in regles(t)


def test_duree_surchargee():
    t = tables([ordo("O1")], [ligne("O1", poso="1 cp x 2/jour pendant 30 jours")])
    assert "ORDONNANCE_FALSIFIEE" in regles(t)


def test_prescripteur_incompatible():
    p = [dict(prestataire_id="P1", type_prestataire="CABINET_SPECIALISTE", specialite="PEDIATRIE",
              statut="ACTIF", numero_onm="ONM-12345", date_fin_convention=None)]
    ref = {**REF, "specs_jugees": {"PEDIATRIE"}, "spec_diag": {("PEDIATRIE", "Asthme")}}
    t = tables([ordo("O1")], [ligne("O1")], presc=p)
    assert "PRESCRIPTEUR_INCOMPATIBLE" in regles(t, ref)


def test_resume_gravite_max():
    t = tables([ordo("O1", date="2024-12-01", diag="Asthme")], [ligne("O1")])
    r = R.resume_par_ordonnance(R.check_ordonnances(t, REF))
    assert r.loc[0, "gravite"] == 3 and r.loc[0, "nb_regles"] == 2
