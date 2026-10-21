"""Pont vers le prétraitement du rôle A.

Contrat : backend/ml/preprocess.py expose
    build_features(payload: dict, conn) -> pandas.DataFrame
qui retourne UNE ligne, avec au moins les colonnes du modèle. C'est la MÊME fonction qu'à
l'entraînement (sinon training/serving skew). `conn` sert aux variables d'historique.

`payload` est la facture validée (contrat de données 11.1) : facture_id, numero_facture,
prestataire_id, assure_id, contrat_id, ordonnance_id, type_facture, date_soin, heure_soin,
devise, lignes[] (code, type_ligne, libelle, quantite, prix_unitaire, montant), montant_total,
nb_lignes... Les colonnes de fuite (statut, motif_rejet, montant_pris_en_charge,
reste_a_charge, date_traitement) n'y figurent JAMAIS : à l'entraînement, utiliser la vue
v_factures_features de P1.
"""
import pandas as pd

from ml.features import CATEGORICAL


class FeaturesUnavailableError(Exception):
    """ml.preprocess.build_features n'existe pas encore."""


class FeatureMismatchError(Exception):
    """Les colonnes produites ne correspondent pas au modèle chargé."""


def build_features(payload: dict, conn, expected: list[str]) -> pd.DataFrame:
    try:
        from ml.preprocess import build_features as _build
    except ModuleNotFoundError as exc:
        if exc.name not in ("ml", "ml.preprocess"):
            raise
        raise FeaturesUnavailableError("backend/ml/preprocess.py introuvable") from exc

    df = _build(payload, conn)
    if len(df) != 1:
        raise FeatureMismatchError(f"1 ligne attendue, {len(df)} reçue(s)")
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise FeatureMismatchError(f"colonnes manquantes : {missing}")
    features = df[expected].copy()
    for column in expected:
        try:
            if column in CATEGORICAL:
                features[column] = features[column].astype("category")
            else:
                features[column] = pd.to_numeric(features[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise FeatureMismatchError(
                f"type invalide pour la variable {column}: {features[column].dtype}"
            ) from exc
    return features  # ordre identique à l'entraînement


def build_features_for_invoices(
    payloads: list[dict], conn, expected: list[str]
) -> pd.DataFrame:
    try:
        from ml.preprocess import build_features_for_invoices as _build
    except ModuleNotFoundError as exc:
        if exc.name not in ("ml", "ml.preprocess"):
            raise
        raise FeaturesUnavailableError("backend/ml/preprocess.py introuvable") from exc

    df = _build(payloads, conn)
    missing = [column for column in expected if column not in df.columns]
    if missing:
        raise FeatureMismatchError(f"colonnes manquantes : {missing}")
    features = df[expected].copy()
    for column in expected:
        try:
            if column in CATEGORICAL:
                features[column] = features[column].astype("category")
            else:
                features[column] = pd.to_numeric(features[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise FeatureMismatchError(
                f"type invalide pour la variable {column}: {features[column].dtype}"
            ) from exc
    return features
