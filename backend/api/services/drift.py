"""Suivi de dérive (P3-19) : PSI (Population Stability Index) sur quelques variables clés.

PSI = somme sur les classes de (part_courante - part_référence) * ln(part_courante / part_référence).
Lecture usuelle : < 0,10 stable ; 0,10 à 0,25 dérive modérée ; > 0,25 dérive forte.

Référence : par défaut, les premières prédictions enregistrées (distribution de départ).
Limite connue : idéalement la référence est le jeu d'entraînement du modèle (artefact de P2) ;
si P2 le publie dans MLflow, remplacer `reference` par ces valeurs sans changer le reste.
"""
import math
from collections.abc import Sequence

import numpy as np

EPS = 1e-4
PSI_MODERE = 0.10
PSI_FORT = 0.25
MAX_CATEGORIES = 10      # en dessous : variable traitée comme catégorielle


def interpret(psi_value: float) -> str:
    if psi_value < PSI_MODERE:
        return "stable"
    if psi_value < PSI_FORT:
        return "moderee"
    return "forte"


def _clean_numeric(values: Sequence) -> list[float]:
    out = []
    for v in values:
        if isinstance(v, bool):
            out.append(float(v))
        elif isinstance(v, (int, float)) and math.isfinite(v):
            out.append(float(v))
    return out


def _psi_from_counts(ref_counts: np.ndarray, cur_counts: np.ndarray) -> float:
    ref = np.clip(ref_counts / max(ref_counts.sum(), 1), EPS, None)
    cur = np.clip(cur_counts / max(cur_counts.sum(), 1), EPS, None)
    return float(np.sum((cur - ref) * np.log(cur / ref)))


def psi(reference: Sequence, current: Sequence, bins: int = 10) -> float | None:
    """PSI entre deux échantillons numériques. None si un échantillon est vide."""
    ref, cur = _clean_numeric(reference), _clean_numeric(current)
    if not ref or not cur:
        return None
    ref_a, cur_a = np.asarray(ref), np.asarray(cur)

    uniques = np.unique(ref_a)
    if len(uniques) <= MAX_CATEGORIES:
        # variable discrète (ex. 0/1) : une classe par valeur de référence + une classe « autre »
        ref_counts = np.array([(ref_a == u).sum() for u in uniques] + [0], dtype=float)
        cur_counts = np.array([(cur_a == u).sum() for u in uniques]
                              + [(~np.isin(cur_a, uniques)).sum()], dtype=float)
        return _psi_from_counts(ref_counts, cur_counts)

    edges = np.unique(np.quantile(ref_a, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    ref_counts, _ = np.histogram(ref_a, bins=edges)
    cur_counts, _ = np.histogram(cur_a, bins=edges)
    return _psi_from_counts(ref_counts.astype(float), cur_counts.astype(float))


def compute_drift(
    reference_rows: list[dict],
    current_rows: list[dict],
    features: list[str],
    min_samples: int = 30,
) -> dict:
    """Calcule le PSI de chaque variable clé ; statut global = pire des variables."""
    if len(reference_rows) < min_samples or len(current_rows) < min_samples:
        return {
            "statut": "donnees_insuffisantes",
            "psi_max": None,
            "n_reference": len(reference_rows),
            "n_courant": len(current_rows),
            "min_echantillon": min_samples,
            "variables": [],
        }
    results = []
    for name in features:
        value = psi([r.get(name) for r in reference_rows], [r.get(name) for r in current_rows])
        if value is None:
            continue
        results.append({"variable": name, "psi": round(value, 4), "niveau": interpret(value)})
    results.sort(key=lambda x: x["psi"], reverse=True)
    worst = results[0]["psi"] if results else None
    return {
        "statut": interpret(worst) if worst is not None else "donnees_insuffisantes",
        "psi_max": worst,
        "n_reference": len(reference_rows),
        "n_courant": len(current_rows),
        "min_echantillon": min_samples,
        "variables": results,
    }
