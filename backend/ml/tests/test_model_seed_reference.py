"""model_seed ne doit plus écraser un échantillon de référence réel par une ligne factice."""
import sys
from pathlib import Path

ML_DIR = Path(__file__).resolve().parents[1]
BACKEND = ML_DIR.parent
for _p in (str(BACKEND), str(ML_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import json

from api import model_seed

FEATURES = ["montant", "type"]
CATEGORIES = {"type": ["A", "B"]}
REAL = [{"montant": 10.0, "type": "A"}, {"montant": None, "type": "B"}]


def _artifact(**extra):
    return {"features": FEATURES, "categories": CATEGORIES, **extra}


def _rows(directory):
    return json.loads((directory / "reference_sample.json").read_text(encoding="utf-8"))["rows"]


def test_les_lignes_de_l_artefact_sont_ecrites(tmp_path):
    model_seed._write_derived_files(tmp_path, _artifact(reference_rows=REAL))
    assert _rows(tmp_path) == REAL


def test_un_echantillon_valide_existant_est_conserve(tmp_path):
    (tmp_path / "reference_sample.json").write_text(json.dumps({"rows": REAL}), encoding="utf-8")
    model_seed._write_derived_files(tmp_path, _artifact())
    assert _rows(tmp_path) == REAL
    # artefact incohérent (mauvaises clés) : on garde aussi l'existant
    model_seed._write_derived_files(tmp_path, _artifact(reference_rows=[{"autre": 1}]))
    assert _rows(tmp_path) == REAL


def test_repli_factice_si_rien_n_existe(tmp_path, capsys):
    model_seed._write_derived_files(tmp_path, _artifact())
    assert _rows(tmp_path) == [{"montant": 0.0, "type": "A"}]
    assert "FACTICE" in capsys.readouterr().err
