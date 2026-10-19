"""Registre des versions du modèle : liste, activation et retour arrière.

    python registry.py list
    python registry.py activate <version>     # bascule (ou retour arrière)

Chaque entraînement crée models/model_<version>.joblib et s'inscrit ici.
`model_active.joblib` est la copie de la version active : l'API la relit sans
redémarrer le code (voir predict.reload()).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent / "models"
REGISTRY = MODELS_DIR / "registry.json"
ACTIVE = MODELS_DIR / "model_active.joblib"


def _read() -> dict:
    if REGISTRY.exists():
        return json.loads(REGISTRY.read_text())
    return {"active": None, "versions": []}


def _write(reg: dict) -> None:
    MODELS_DIR.mkdir(exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, indent=2, ensure_ascii=False))


def register(entry: dict, activate: bool = True) -> None:
    reg = _read()
    reg["versions"] = [v for v in reg["versions"] if v["version"] != entry["version"]] + [entry]
    _write(reg)
    if activate:
        set_active(entry["version"])


def set_active(version: str) -> None:
    reg = _read()
    found = [v for v in reg["versions"] if v["version"] == version]
    if not found:
        raise KeyError(f"version inconnue : {version}")
    src = MODELS_DIR / found[0]["file"]
    if not src.exists():
        raise FileNotFoundError(src)
    shutil.copyfile(src, ACTIVE)
    reg["active"] = version
    for v in reg["versions"]:
        v["status"] = "active" if v["version"] == version else "archived"
    _write(reg)


def versions() -> list[dict]:
    return _read()["versions"]


def active_version() -> str | None:
    return _read()["active"]


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        for v in versions():
            m = v.get("test", {})
            print(f"{'*' if v['version'] == active_version() else ' '} {v['version']:<34} "
                  f"{v['trained_at']}  PR-AUC={m.get('pr_auc')}  rappel={m.get('recall')}")
    elif cmd == "activate" and len(sys.argv) > 2:
        set_active(sys.argv[2])
        print("version active :", sys.argv[2])
    else:
        sys.exit(__doc__)
