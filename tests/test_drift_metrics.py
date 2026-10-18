"""Tests purs (sans FastAPI ni base) : PSI de dérive (P3-19) et métriques HTTP (P3-18)."""
import numpy as np

from api.services.drift import compute_drift, interpret, psi
from api.services.metrics import HttpMetrics

RNG = np.random.default_rng(42)


def test_psi_same_distribution_is_stable():
    a, b = RNG.normal(0, 1, 3000), RNG.normal(0, 1, 3000)
    assert psi(a, b) < 0.1
    assert interpret(psi(a, b)) == "stable"


def test_psi_shifted_distribution_is_strong_drift():
    a, b = RNG.normal(0, 1, 3000), RNG.normal(1.5, 1, 3000)
    assert psi(a, b) > 0.25
    assert interpret(psi(a, b)) == "forte"


def test_psi_binary_variable():
    assert psi([0] * 900 + [1] * 100, [0] * 900 + [1] * 100) == 0.0
    assert psi([0] * 900 + [1] * 100, [0] * 500 + [1] * 500) > 0.25


def test_psi_unseen_category_is_detected():
    assert psi([1] * 100, [1] * 50 + [2] * 50) > 0.25


def test_psi_empty_or_non_numeric_is_none():
    assert psi([], [1, 2, 3]) is None
    assert psi(["a", "b"], ["a"]) is None
    assert psi([None, float("nan")], [1.0]) is None


def test_compute_drift_flags_the_drifting_variable_only():
    a = RNG.normal(0, 1, 200)
    ref = [{"x": float(v), "stable": float(RNG.normal())} for v in a]
    cur = [{"x": float(v) + 3, "stable": float(RNG.normal())} for v in RNG.normal(0, 1, 200)]
    res = compute_drift(ref, cur, ["x", "stable", "absente"], min_samples=30)
    by_name = {v["variable"]: v for v in res["variables"]}
    assert by_name["x"]["niveau"] == "forte"
    assert by_name["stable"]["niveau"] == "stable"
    assert "absente" not in by_name           # variable inconnue ignorée, pas d'erreur
    assert res["statut"] == "forte" and res["psi_max"] == by_name["x"]["psi"]


def test_compute_drift_needs_enough_samples():
    res = compute_drift([{"x": 1.0}] * 5, [{"x": 2.0}] * 5, ["x"], min_samples=30)
    assert res["statut"] == "donnees_insuffisantes" and res["psi_max"] is None


def test_http_metrics_counts_errors_and_latency():
    m = HttpMetrics()
    for i in range(10):
        m.record("POST", "/predict", 200, 10 + i)
    m.record("POST", "/predict", 500, 300)
    m.record("GET", "/alerts", 403, 2)
    s = m.snapshot()
    assert s["requetes_total"] == 12
    assert s["erreurs_5xx"] == 1 and s["erreurs_4xx"] == 1
    assert s["routes"]["POST /predict"]["count"] == 11
    assert s["routes"]["POST /predict"]["latence_ms"]["max"] == 300.0
    assert s["taux_erreur_5xx"] == round(1 / 12, 4)


def test_http_metrics_window_is_bounded():
    m = HttpMetrics()
    for _ in range(5000):
        m.record("GET", "/health", 200, 1.0)
    assert m.snapshot()["routes"]["GET /health"]["count"] == 5000   # le compteur reste exact
