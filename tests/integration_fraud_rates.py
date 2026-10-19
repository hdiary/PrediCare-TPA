"""Compare Phase 5b rule rates with labels on the PostgreSQL dataset."""
import os

import pandas as pd
import psycopg

from ml.features import TABLES, build_features


def frame(conn, table):
    cur = conn.execute(f"SELECT * FROM {table}")
    return pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])


def main():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        tables = {name: frame(conn, name) for name in TABLES}
        labels = frame(conn, "labels_fraude")[["facture_id", "est_fraude", "type_fraude"]]
    X, _ = build_features(tables)
    flags = pd.DataFrame(index=X.index)
    flags["QUANTITE_EXCESSIVE"] = X["l_q_ratio_max"] > 1.2
    flags["LIGNES_NON_PRESCRITES"] = X["l_n_hors_ordo"] > 0
    flags["SUBSTITUTION_PRODUIT"] = X["l_n_non_remboursable"] > 0
    flags["ORDONNANCE_EXPIREE"] = X["ordo_exp_jours"] > 0
    flags["SOINS_JOUR_FERME"] = X["jour_ferme"] == 1
    flags["DOUBLON"] = (X["dup_numero"] > 1) & (X["dup_numero_rang"] > 0)
    flags["FRACTIONNEMENT"] = (X["meme_jour_n"] > 1) & (X["meme_jour_rang"] > 0)
    flags["SURCONSOMMATION"] = (X["ordo_n_factures"] > 1) & (X["ordo_rang_usage"] > 0)
    flags["ACTE_FICTIF"] = X["ordo_manquante_requise"] == 1
    flags["INCOHERENCE_PROFIL"] = (X["l_n_viol_age"] + X["l_n_viol_sexe"]) > 0
    joined = labels.set_index("facture_id").join(flags, how="inner")
    output = {}
    for code in flags.columns:
        output[code] = {}
        for truth in (True, False):
            subset = joined[joined["est_fraude"] == truth]
            output[code][str(truth).lower()] = {
                "triggered": int(subset[code].sum()),
                "total": int(len(subset)),
                "rate": float(subset[code].mean()) if len(subset) else 0.0,
                "label_frequency": float((subset["type_fraude"] == code).mean()) if len(subset) else 0.0,
            }
    print(output)


if __name__ == "__main__":
    main()
