"""Entraînement P2 : détection de fraude (classification binaire est_fraude).

Usage :
    python train.py --dataset ../../data/dataset --labels ../../data/labels \
                    --algo hgb            # ou lightgbm / xgboost / all

Protocole :
  * split train/test 80/20 GROUPÉ par assuré (doublons, fractionnements et
    ordonnances réutilisées restent du même côté : pas de fuite) ;
  * validation croisée groupée (5 plis) sur le train -> prédictions OOF ;
  * seuil choisi sur les OOF : le plus élevé qui garantit Recall >= --recall ;
  * évaluation finale sur le test (jamais vu pendant le choix du seuil).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (average_precision_score, precision_recall_curve,
                             roc_auc_score)
from sklearn.model_selection import GroupKFold, GroupShuffleSplit

import features as F

HERE = Path(__file__).resolve().parent
MODELS_DIR = HERE / "models"
SEED = 42


def read_labels(path: Path) -> pd.DataFrame:
    p = Path(path)
    if p.is_dir():
        p = next(p.glob("labels_fraude.*"))
    df = pd.read_excel(p) if p.suffix in (".xlsx", ".xls") else pd.read_csv(p)
    return df.set_index("facture_id")


def make_model(algo: str, pos_weight: float):
    if algo == "hgb":
        # sklearn >= 1.4 : gère NaN et variables catégorielles nativement
        return HistGradientBoostingClassifier(
            learning_rate=0.06, max_iter=500, max_leaf_nodes=31, min_samples_leaf=30,
            l2_regularization=1.0, early_stopping=True, validation_fraction=0.1,
            n_iter_no_change=30, categorical_features="from_dtype",
            class_weight={0: 1.0, 1: pos_weight}, random_state=SEED)
    if algo == "lightgbm":
        from lightgbm import LGBMClassifier
        return LGBMClassifier(
            n_estimators=600, learning_rate=0.05, num_leaves=31, min_child_samples=30,
            subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
            scale_pos_weight=pos_weight, random_state=SEED, verbose=-1)
    if algo == "xgboost":
        from xgboost import XGBClassifier
        return XGBClassifier(
            n_estimators=600, learning_rate=0.05, max_depth=6, subsample=0.8,
            colsample_bytree=0.8, min_child_weight=3, reg_lambda=1.0,
            scale_pos_weight=pos_weight, tree_method="hist", enable_categorical=True,
            eval_metric="aucpr", random_state=SEED, n_jobs=-1)
    raise ValueError(algo)


def pick_threshold(y, p, recall_target: float) -> float:
    prec, rec, thr = precision_recall_curve(y, p)
    ok = np.where(rec[:-1] >= recall_target)[0]
    return float(thr[ok[-1]]) if len(ok) else float(thr[0])


def report(y, p, thr) -> dict:
    pred = p >= thr
    tp = int((pred & (y == 1)).sum())
    fp = int((pred & (y == 0)).sum())
    fn = int((~pred & (y == 1)).sum())
    return {
        "pr_auc": round(float(average_precision_score(y, p)), 4),
        "roc_auc": round(float(roc_auc_score(y, p)), 4),
        "seuil": round(float(thr), 4),
        "recall": round(tp / max(tp + fn, 1), 4),
        "precision": round(tp / max(tp + fp, 1), 4),
        "alertes": int(pred.sum()), "tp": tp, "fp": fp, "fn": fn,
    }


def run(algo: str, X, y, groups, recall_target: float):
    pos_weight = float((y == 0).sum() / max((y == 1).sum(), 1))
    tr, te = next(GroupShuffleSplit(1, test_size=0.2, random_state=SEED).split(X, y, groups))
    Xtr, ytr, gtr = X.iloc[tr], y.iloc[tr], groups.iloc[tr]
    Xte, yte = X.iloc[te], y.iloc[te]

    oof = np.zeros(len(Xtr))
    for k, (a, b) in enumerate(GroupKFold(5).split(Xtr, ytr, gtr)):
        m = make_model(algo, pos_weight).fit(Xtr.iloc[a], ytr.iloc[a])
        oof[b] = m.predict_proba(Xtr.iloc[b])[:, 1]
    thr = pick_threshold(ytr.values, oof, recall_target)
    cv = report(ytr.values, oof, thr)

    final = make_model(algo, pos_weight).fit(Xtr, ytr)
    pte = final.predict_proba(Xte)[:, 1]
    test = report(yte.values, pte, thr)
    return final, thr, cv, test, (te, pte)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--algo", default="hgb", choices=["hgb", "lightgbm", "xgboost", "all"])
    ap.add_argument("--recall", type=float, default=0.95, help="Recall cible pour le seuil")
    a = ap.parse_args()

    X, meta = F.build_features(F.load_tables(a.dataset))
    lab = read_labels(a.labels).reindex(X.index)
    y = lab["est_fraude"].astype(int)
    groups = meta["assure_id"]
    print(f"{len(X)} factures, {X.shape[1]} features, taux de fraude {y.mean():.2%}")

    algos = ["hgb", "lightgbm", "xgboost"] if a.algo == "all" else [a.algo]
    MODELS_DIR.mkdir(exist_ok=True)
    results = {}
    for algo in algos:
        try:
            model, thr, cv, test, (te, pte) = run(algo, X, y, groups, a.recall)
        except ImportError:
            print(f"[{algo}] bibliothèque non installée -> ignoré")
            continue
        print(f"\n== {algo}\n  CV   : {cv}\n  TEST : {test}")
        types = lab["type_fraude"].iloc[te]
        yte = y.iloc[te].values
        par_type = {}
        for ty in sorted(types.dropna().unique()):
            mask = (types == ty).values
            par_type[ty] = {"n": int(mask.sum()),
                            "recall": round(float((pte[mask] >= thr).mean()), 3)}
        results[algo] = {"cv": cv, "test": test, "recall_par_type": par_type}
        joblib.dump({"model": model, "features": list(X.columns), "seuil": thr,
                     "algo": algo, "categories": {c: list(X[c].cat.categories)
                                                   for c in F.CATEGORICAL}},
                    MODELS_DIR / f"model_{algo}.joblib")

    (MODELS_DIR / "metrics.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
    best = max(results, key=lambda k: results[k]["test"]["pr_auc"])
    print(f"\nMeilleur modèle (PR-AUC test) : {best}")
    joblib.dump(joblib.load(MODELS_DIR / f"model_{best}.joblib"), MODELS_DIR / "model_active.joblib")


if __name__ == "__main__":
    main()
