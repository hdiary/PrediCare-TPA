from datetime import date

from api.services.prescription_anomalies import (
    rule_ordonnance_antidatee,
    rule_ordonnance_falsifiee,
    rule_prescripteur_incompatible,
    rule_prescripteur_radie,
)


class Conn:
    def __init__(self, threshold=10):
        self.threshold = threshold

    def execute(self, sql, params=()):
        class Result:
            def __init__(self, threshold):
                self.threshold = threshold

            def fetchone(self):
                return {"valeur": str(self.threshold)}

        return Result(self.threshold)


def ordonnance(**overrides):
    value = {"date_prescription": date(2026, 1, 10)}
    value.update(overrides)
    return value


def test_ordonnance_falsifiee_positive_and_negative():
    conn = Conn(10)
    assert rule_ordonnance_falsifiee(conn, ordonnance(), [{"code": "A", "quantite": 11}], {})
    assert rule_ordonnance_falsifiee(conn, ordonnance(), [{"code": "A", "quantite": 10}], {}) is None


def test_prescripteur_incompatible_positive_and_negative():
    context = {"prescripteur": {"specialite": "CARDIO"}, "actes": {"A": {"specialite": "DENTAIRE"}}}
    assert rule_prescripteur_incompatible(Conn(), ordonnance(), [{"code": "A"}], context)
    context["actes"]["A"]["specialite"] = "CARDIO"
    assert rule_prescripteur_incompatible(Conn(), ordonnance(), [{"code": "A"}], context) is None


def test_prescripteur_radie_positive_and_negative():
    context = {"prescripteur": {"date_fin_convention": date(2026, 1, 9)}}
    assert rule_prescripteur_radie(Conn(), ordonnance(), [], context)
    context["prescripteur"]["date_fin_convention"] = date(2026, 1, 10)
    assert rule_prescripteur_radie(Conn(), ordonnance(), [], context) is None


def test_ordonnance_antidatee_positive_and_negative():
    context = {"assure": {"date_adhesion": date(2026, 1, 11)}}
    assert rule_ordonnance_antidatee(Conn(), ordonnance(), [], context)
    context["assure"]["date_adhesion"] = date(2026, 1, 10)
    assert rule_ordonnance_antidatee(Conn(), ordonnance(), [], context) is None
