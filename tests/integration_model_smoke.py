"""Load the active seed through the real registry and run score + SHAP."""
import os
import json
from pathlib import Path
import pandas as pd
import psycopg
from psycopg.rows import dict_row

from api.services.model_registry import registry


def main():
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        bundle = registry.initialize(conn)
        record = conn.execute("SELECT artifact_path FROM model_versions WHERE status='ACTIF'").fetchone()
        sample = json.loads((Path(record["artifact_path"]).parent / "reference_sample.json").read_text())
        schema = json.loads((Path(record["artifact_path"]).parent / "feature_schema.json").read_text())
        row = pd.DataFrame(sample["rows"], columns=schema["features"]).iloc[[0]]
        for name, values in schema.get("categories", {}).items():
            row[name] = pd.Categorical(row[name], categories=values)
        score = float(bundle.model.predict_proba(row)[0][-1])
        shap_values = bundle.explainer.shap_values(row)
        print({"version_modele": bundle.version, "score": score, "shap_non_vide": shap_values is not None and len(shap_values) > 0})
        assert 0 <= score <= 1
        assert shap_values is not None


if __name__ == "__main__":
    main()
