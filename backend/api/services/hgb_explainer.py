"""Explications SHAP pour les modèles HGB (sans TreeExplainer).

Les valeurs sont exprimées en probabilité et calculées par rapport à un FOND de factures de
référence (`reference_sample.json`). La valeur de base est le score moyen du modèle sur ce
fond : il doit donc être composé de factures légitimes représentatives, sinon la base n'a
aucun sens métier (une ligne factice remplie de zéros peut elle-même scorer 0,94).
"""

MAX_BACKGROUND_ROWS = 25


class HGBPermutationExplainer:
    def __init__(self, model, reference, features: list[str], categories: dict,
                 max_background: int = MAX_BACKGROUND_ROWS):
        import numpy as np
        import pandas as pd
        import shap

        self.features = features
        self.categories = categories
        background = reference.head(max_background)
        encoded_background = self._encode(background, pd)
        # Base = score moyen sur le fond (et non le score de la première ligne seulement).
        self.expected_value = np.asarray(model.predict_proba(background)).mean(axis=0)
        self._explainer = shap.PermutationExplainer(
            self._predict_proba(model, pd), encoded_background,
            feature_names=features,
        )

    def _encode(self, frame, pandas):
        encoded = frame.copy()
        for name, levels in self.categories.items():
            encoded[name] = pandas.Categorical(
                frame[name], categories=levels
            ).codes.astype(float)
        encoded = encoded.apply(pandas.to_numeric, errors="raise")
        return encoded.to_numpy(dtype="float64")

    def _predict_proba(self, model, pandas):
        import numpy as np

        def predict(values):
            frame = pandas.DataFrame(values, columns=self.features)
            for name, levels in self.categories.items():
                codes = np.rint(
                    pandas.to_numeric(frame[name], errors="coerce")
                ).astype("Int64")
                frame[name] = pandas.Categorical(
                    [
                        levels[int(code)]
                        if not pandas.isna(code) and 0 <= int(code) < len(levels)
                        else None
                        for code in codes
                    ],
                    categories=levels,
                )
            return model.predict_proba(frame)

        return predict

    def shap_values(self, frame):
        import pandas as pd

        encoded = self._encode(frame, pd)
        min_evals = 2 * self._explainer.masker.shape[1] + 1
        return self._explainer(encoded, max_evals=min_evals).values
