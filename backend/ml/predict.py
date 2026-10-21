"""Inférence : score des factures avec le modèle ACTIF du registre.

* validation des entrées : colonne manquante ou donnée absurde -> erreur claire, jamais de
  plantage obscur (cahier de recette S10, lot de factures inédites) ;
* chaque résultat porte la version du modèle (journal d'audit, S8) ;
* `reload()` relit le modèle actif après un changement de version, sans redémarrer.

Les variables « de groupe » (doublons, ordonnance réutilisée, volume prestataire) ont
besoin de l'historique : calculez-les sur la base complète (factures déjà reçues + les
nouvelles) avec features.build_features, puis gardez les lignes à scorer.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

import registry
from calibration import calibrated_probability

_ART: dict | None = None


class EntreeInvalide(ValueError):
    """Les données fournies ne permettent pas de calculer un score."""


def reload(path: str | Path | None = None) -> dict:
    global _ART
    _ART = joblib.load(path or registry.ACTIVE)
    return _ART


def load() -> dict:
    return _ART if _ART is not None else reload()


def version() -> str:
    return load().get("version", "inconnue")


def validate(X: pd.DataFrame, art: dict | None = None) -> pd.DataFrame:
    """Retourne une copie propre, ou lève EntreeInvalide."""
    art = art or load()
    if not isinstance(X, pd.DataFrame):
        raise EntreeInvalide("les variables doivent être fournies sous forme de DataFrame")
    if X.empty:
        raise EntreeInvalide("aucune facture à scorer")
    manquantes = [c for c in art["features"] if c not in X.columns]
    if manquantes:
        raise EntreeInvalide(f"variables manquantes : {', '.join(manquantes)}")
    X = X[art["features"]].copy()
    cats = art.get("categories", {})
    for c in X.columns:
        if c in cats:  # catégorie inconnue -> valeur manquante (le modèle sait la traiter)
            X[c] = pd.Categorical(X[c], categories=cats[c])
        else:
            X[c] = pd.to_numeric(X[c], errors="coerce").replace([np.inf, -np.inf], np.nan)
    return X


def score(X: pd.DataFrame, seuil: float | None = None) -> pd.DataFrame:
    """Colonnes : score (0-1), alerte (bool), model_version. `seuil` remplace celui du modèle
    (réglable en direct depuis l'écran d'administration)."""
    art = load()
    X = validate(X, art)
    p = calibrated_probability(art["model"], art.get("calibrator"), X)
    s = art["seuil"] if seuil is None else seuil
    return pd.DataFrame({"score": p, "alerte": p >= s, "model_version": version()}, index=X.index)
