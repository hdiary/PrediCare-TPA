"""Régénère reference_sample.json des versions de models_seed avec de vraies factures légitimes.

    python make_reference_sample.py --dataset ../../dataset --labels ../../labels [--rows 25]
    python make_reference_sample.py ... --version vhgb-20261016-0807-b2ead0

Le fond est tiré dans la fenêtre d'ENTRAÎNEMENT (même découpage temporel que train.py), parmi les
factures non frauduleuses. api/model_seed.py conserve ensuite ces fichiers (il ne réécrit plus la
ligne factice si un échantillon valide existe) et ml_service les resynchronise vers le store.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import features as F
import train as T
from reference import N_REFERENCE, reference_rows

SEED_ROOT = Path(__file__).resolve().parent / "models_seed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--rows", type=int, default=N_REFERENCE)
    ap.add_argument("--version", action="append", help="nom de dossier models_seed (défaut : tous)")
    a = ap.parse_args()

    X, meta = F.build_features(F.load_tables(a.dataset))
    y = T.read_labels(a.labels).reindex(X.index)["est_fraude"].astype(int)
    itr, _, _ = T.temporal_split(meta["date_soin"])
    Xtr, ytr = X.iloc[itr], y.iloc[itr]

    dirs = [SEED_ROOT / v for v in a.version] if a.version else sorted(SEED_ROOT.glob("v*"))
    for d in dirs:
        schema_path = d / "feature_schema.json"
        if not schema_path.is_file():
            print(f"[ignoré] {d.name} : feature_schema.json absent")
            continue
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        features = schema["features"]
        missing = [c for c in features if c not in Xtr.columns]
        if missing:
            print(f"[ignoré] {d.name} : variables absentes de features.py : {missing}")
            continue
        rows = reference_rows(Xtr, ytr, n=a.rows, features=features)
        for row in rows:  # catégorie inconnue du schéma -> manquante
            for name, levels in schema.get("categories", {}).items():
                if row[name] not in levels:
                    row[name] = None
        (d / "reference_sample.json").write_text(
            json.dumps({"rows": rows}, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"[ok] {d.name} : {len(rows)} factures légitimes de référence")


if __name__ == "__main__":
    main()
