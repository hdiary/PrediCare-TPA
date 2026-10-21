"""Entraînement P2 v2 : détection de fraude (est_fraude), protocole du Kanban.

    python train.py --dataset ../../dataset --labels ../../labels --algo all

Protocole
  * découpage temporel par quantiles date_soin : 60 % train, 8 % sélection,
    6 % calibration, 6 % choix du seuil, 20 % test ;
  * calibrateur sigmoid ajusté sur des marges brutes, puis seuil mesuré sur
    une fenêtre ultérieure distincte ;
  * LightGBM régularisé, sans pondération positive, avec arrêt anticipé ;
  * candidats comparés : régression logistique (baseline), puis chaque algorithme
    en « poids de classes » et en « SMOTE » (si imbalanced-learn est installé) ;
  * réglage par recherche aléatoire (--n-iter) sur la PR-AUC de sélection ;
  * seuil choisi sur la fenêtre dédiée (Recall >= --recall) ; test final indépendant ;
  * le meilleur candidat (PR-AUC de sélection) est versionné, enregistré dans
    registry.json et activé ; MLflow est alimenté si la bibliothèque est présente.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.calibration import calibration_curve
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.model_selection import ParameterSampler
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import features as F
import registry
from calibration import calibrated_probability, fit_sigmoid_calibrator, model_margin
from reference import reference_rows

MODELS_DIR = registry.MODELS_DIR
SEED = 42
SEUIL_CDC = 0.8  # seuil de déclenchement n8n cité dans le cahier des charges

GRILLES = {
    "hgb": {"learning_rate": [0.03, 0.06, 0.1], "max_leaf_nodes": [15, 31, 63],
            "min_samples_leaf": [10, 30, 60], "l2_regularization": [0.0, 1.0, 5.0]},
    "lightgbm": {"learning_rate": [0.03, 0.05], "num_leaves": [15, 31],
                 "min_child_samples": [50, 100], "subsample": [0.7, 0.85, 1.0],
                 "colsample_bytree": [0.6, 0.8, 1.0], "reg_lambda": [5.0, 10.0, 20.0]},
    "xgboost": {"learning_rate": [0.03, 0.05, 0.1], "max_depth": [4, 6, 8],
                "min_child_weight": [1, 3, 8], "subsample": [0.7, 0.85, 1.0],
                "colsample_bytree": [0.6, 0.8, 1.0], "reg_lambda": [0.0, 1.0, 5.0]},
}


# ------------------------------------------------------------------ données
def read_labels(path: Path) -> pd.DataFrame:
    p = Path(path)
    if p.is_dir():
        p = next(p.glob("labels_fraude.*"))
    df = pd.read_excel(p) if p.suffix in (".xlsx", ".xls") else pd.read_csv(p)
    return df.set_index("facture_id")


def temporal_split(dates: pd.Series, fr_train=0.60, fr_select=0.68,
                   fr_calibrate=0.74, fr_threshold=0.80):
    """Return chronological train, selection, calibration, threshold and test indices."""
    q1, q2, q3, q4 = dates.quantile(
        [fr_train, fr_select, fr_calibrate, fr_threshold]
    ).values
    return (
        np.where(dates < q1)[0],
        np.where((dates >= q1) & (dates < q2))[0],
        np.where((dates >= q2) & (dates < q3))[0],
        np.where((dates >= q3) & (dates < q4))[0],
        np.where(dates >= q4)[0],
    )


# ------------------------------------------------------------------ modèles
def make_model(algo: str, params: dict, pos_weight: float):
    if algo == "logreg":
        cat = [c for c in F.CATEGORICAL]
        pre = ColumnTransformer([
            ("cat", OneHotEncoder(handle_unknown="ignore"), cat),
        ], remainder=Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)),
                               ("sc", StandardScaler())]))
        return Pipeline([("pre", pre), ("clf", LogisticRegression(
            class_weight="balanced", max_iter=300, C=1.0))])
    if algo == "hgb":
        return HistGradientBoostingClassifier(
            max_iter=400, early_stopping=True, validation_fraction=0.1, n_iter_no_change=25,
            categorical_features="from_dtype", class_weight={0: 1.0, 1: pos_weight},
            random_state=SEED, **params)
    if algo == "lightgbm":
        from lightgbm import LGBMClassifier
        return LGBMClassifier(n_estimators=500, subsample_freq=1, scale_pos_weight=1.0,
                              random_state=SEED, verbose=-1, **params)
    if algo == "xgboost":
        from xgboost import XGBClassifier
        return XGBClassifier(n_estimators=500, tree_method="hist", enable_categorical=True,
                             scale_pos_weight=pos_weight, eval_metric="aucpr",
                             random_state=SEED, n_jobs=-1, **params)
    raise ValueError(algo)


def smote_resample(X: pd.DataFrame, y: pd.Series, ratio: float = 0.3):
    """SMOTE-NC (variables mixtes). Les NaN numériques sont imputés par la médiane."""
    from imblearn.over_sampling import SMOTENC
    cats = [c for c in F.CATEGORICAL if c in X.columns]
    nums = [c for c in X.columns if c not in cats]
    Z = X.copy()
    Z[nums] = Z[nums].fillna(Z[nums].median()).astype(float)
    levels = {c: Z[c].cat.categories for c in cats}
    for c in cats:
        Z[c] = Z[c].cat.codes.astype(int)  # -1 = valeur manquante
    sm = SMOTENC(categorical_features=[Z.columns.get_loc(c) for c in cats],
                 sampling_strategy=ratio, random_state=SEED)
    Zr, yr = sm.fit_resample(Z, y)
    Zr = pd.DataFrame(Zr, columns=Z.columns)
    Zr[nums] = Zr[nums].astype(float)
    for c in cats:
        Zr[c] = pd.Categorical.from_codes(Zr[c].astype(int), categories=levels[c])
    return Zr, pd.Series(yr)


# ------------------------------------------------------------------ métriques
def pick_threshold(y, p, recall_target: float) -> float:
    prec, rec, thr = precision_recall_curve(y, p)
    ok = np.where(rec[:-1] >= recall_target)[0]
    return float(thr[ok[-1]]) if len(ok) else float(thr[0])


def at(y, p, thr) -> dict:
    pred = p >= thr
    tp = int((pred & (y == 1)).sum()); fp = int((pred & (y == 0)).sum()); fn = int((~pred & (y == 1)).sum())
    return {"seuil": round(float(thr), 4), "recall": round(tp / max(tp + fn, 1), 4),
            "precision": round(tp / max(tp + fp, 1), 4), "alertes": int(pred.sum()),
            "tp": tp, "fp": fp, "fn": fn}


def full_report(y, p, thr) -> dict:
    observed, predicted = calibration_curve(y, p, n_bins=10, strategy="quantile")
    curve = [{"score_moyen": round(float(x), 6), "frequence_observee": round(float(yhat), 6)}
             for x, yhat in zip(predicted, observed)]
    return {"pr_auc": round(float(average_precision_score(y, p)), 4),
            "roc_auc": round(float(roc_auc_score(y, p)), 4),
            "brier_score": round(float(brier_score_loss(y, p)), 6),
            "courbe_calibration": curve, **at(y, p, thr),
            "au_seuil_cdc": at(y, p, SEUIL_CDC)}


def _fit_candidate(model, algo, Xfit, yfit, Xselect, yselect):
    if algo == "lightgbm":
        from lightgbm import early_stopping
        model.fit(
            Xfit,
            yfit,
            eval_X=(Xselect,),
            eval_y=(yselect,),
            eval_metric="binary_logloss",
            callbacks=[early_stopping(stopping_rounds=50, verbose=False)],
        )
        return model
    return model.fit(Xfit, yfit)


# ------------------------------------------------------------------ candidat
def run_candidate(name, algo, strat, data, n_iter):
    Xtr, ytr, Xselect, yselect = data[:4]
    pw = float((ytr == 0).sum() / max((ytr == 1).sum(), 1))
    if strat == "smote":
        Xfit, yfit = smote_resample(Xtr, ytr)
        pw = 1.0
    else:
        Xfit, yfit = Xtr, ytr
    cand = ([{}] if algo == "logreg" else
            list(ParameterSampler(GRILLES[algo], n_iter=n_iter, random_state=SEED)))
    best = None
    for params in cand:
        t0 = time.time()
        m = _fit_candidate(make_model(algo, params, pw), algo, Xfit, yfit, Xselect, yselect)
        pv = model_margin(m, Xselect)
        score = average_precision_score(yselect, pv)
        print(f"    {name:<22} {params} -> PR-AUC sélection {score:.4f} ({time.time() - t0:.0f}s)")
        if best is None or score > best[0]:
            best = (score, params, m, pv)
    score, params, model, _ = best
    return {"name": name, "algo": algo, "strategie": strat, "params": params, "model": model,
            "selection_pr_auc": float(score)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--algo", default="hgb", choices=["hgb", "lightgbm", "xgboost", "all"])
    ap.add_argument("--recall", type=float, default=0.95, help="Recall cible pour le seuil")
    ap.add_argument("--n-iter", type=int, default=12, help="essais de la recherche aléatoire")
    ap.add_argument("--no-smote", action="store_true")
    a = ap.parse_args()

    X, meta = F.build_features(F.load_tables(a.dataset))
    lab = read_labels(a.labels).reindex(X.index)
    y = lab["est_fraude"].astype(int)
    itr, iselect, ical, ithr, ite = temporal_split(meta["date_soin"])
    data = (X.iloc[itr], y.iloc[itr], X.iloc[iselect], y.iloc[iselect])
    fen = {k: [str(meta["date_soin"].iloc[i].min().date()), str(meta["date_soin"].iloc[i].max().date())]
           for k, i in (("train", itr), ("selection", iselect), ("calibration", ical),
                        ("threshold", ithr), ("test", ite))}
    print(f"{len(X)} factures, {X.shape[1]} variables, fraude {y.mean():.2%} | fenêtres {fen}")

    try:
        import imblearn  # noqa: F401
        smote_ok = not a.no_smote
    except ImportError:
        smote_ok = False
        print("[SMOTE] imbalanced-learn absent -> comparaison SMOTE ignorée")

    algos = ["hgb", "lightgbm", "xgboost"] if a.algo == "all" else [a.algo]
    plan = [("baseline_logreg", "logreg", "poids")]
    for g in algos:
        strategy = "sans_ponderation" if g == "lightgbm" else "poids"
        suffix = "regularise" if g == "lightgbm" else "poids"
        plan.append((f"{g}_{suffix}", g, strategy))
        if smote_ok:
            plan.append((f"{g}_smote", g, "smote"))

    res = []
    for name, algo, strat in plan:
        print(f"\n== {name}")
        try:
            res.append(run_candidate(name, algo, strat, data, a.n_iter))
        except ImportError as e:
            print(f"   ignoré (bibliothèque absente) : {e}")

    tab = pd.DataFrame([{"candidat": r["name"], "pr_auc_selection": round(r["selection_pr_auc"], 4)}
                        for r in res])
    print("\n" + tab.to_string(index=False))
    MODELS_DIR.mkdir(exist_ok=True)
    tab.to_csv(MODELS_DIR / "comparison.csv", index=False)

    # Le jeu de test reste indépendant du choix du modèle et du seuil.
    pool = [r for r in res if r["algo"] != "logreg"] or res
    best = max(pool, key=lambda r: r["selection_pr_auc"])
    Xcal, ycal = X.iloc[ical], y.iloc[ical]
    Xthr, ythr = X.iloc[ithr], y.iloc[ithr]
    Xtest, ytest = X.iloc[ite], y.iloc[ite]
    calibrator = fit_sigmoid_calibrator(best["model"], Xcal, ycal)
    p_threshold = calibrated_probability(best["model"], calibrator, Xthr)
    threshold = pick_threshold(ythr.values, p_threshold, a.recall)
    p_test = calibrated_probability(best["model"], calibrator, Xtest)
    raw_p_test = calibrated_probability(best["model"], None, Xtest)
    valid_report = full_report(ythr.values, p_threshold, threshold)
    test_report = full_report(ytest.values, p_test, threshold)
    raw_test_report = full_report(ytest.values, raw_p_test, 0.5)
    types = lab["type_fraude"].iloc[ite]
    par_type = {t: {"n": int((types == t).sum()),
                    "recall": round(float((p_test[(types == t).values] >= threshold).mean()), 3)}
                for t in sorted(types.dropna().unique())}

    h = hashlib.sha1(json.dumps([best["name"], best["params"], list(X.columns)], default=str).encode()).hexdigest()[:6]
    version = f"{best['algo']}-{datetime.now(timezone.utc):%Y%m%d-%H%M}-{h}"
    fichier = f"model_{version}.joblib"
    joblib.dump({"model": best["model"], "calibrator": calibrator,
                 "calibration": {"method": "sigmoid", "input": "raw_model_margin"},
                 "features": list(X.columns), "seuil": threshold,
                 "algo": best["algo"], "strategie": best["strategie"], "params": best["params"],
                 "version": version, "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "fenetres": fen, "seuil_cdc": SEUIL_CDC,
                 "categories": {c: list(X[c].cat.categories) for c in F.CATEGORICAL},
                 # fond des explications SHAP : factures légitimes de la fenêtre d'entraînement
                 "reference_rows": reference_rows(data[0], data[1], seed=SEED)},
                MODELS_DIR / fichier)
    entry = {"version": version, "file": fichier, "algo": best["algo"], "strategie": best["strategie"],
             "params": best["params"], "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "seuil": round(threshold, 6), "valid": valid_report, "test": test_report,
             "selection_pr_auc": round(best["selection_pr_auc"], 4),
             "test_non_calibre": raw_test_report,
             "recall_par_type": par_type, "fenetres": fen, "status": "active"}
    registry.register(entry, activate=True)
    (MODELS_DIR / "metrics.json").write_text(json.dumps(
        {"version": version, "comparaison": tab.to_dict("records"), "retenu": entry},
        indent=2, ensure_ascii=False, default=str))

    try:  # suivi des expériences, si MLflow est installé
        import mlflow
        mlflow.set_experiment("predicare-fraude")
        with mlflow.start_run(run_name=version):
            mlflow.log_params({"algo": best["algo"], "strategie": best["strategie"], **best["params"]})
            mlflow.log_metrics({"pr_auc_test": test_report["pr_auc"], "recall_test": test_report["recall"],
                                "precision_test": test_report["precision"],
                                "brier_test": test_report["brier_score"], "seuil": threshold})
            mlflow.log_artifact(str(MODELS_DIR / fichier))
    except ImportError:
        print("[MLflow] non installé -> suivi ignoré (registry.json tient lieu de registre)")

    print(f"\nModèle retenu : {version}\n  test calibré : {test_report}\n"
          f"  test brut : {raw_test_report}\n  recall par type : "
          f"{ {k: v['recall'] for k, v in par_type.items()} }")


if __name__ == "__main__":
    main()
