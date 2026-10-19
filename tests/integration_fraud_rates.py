"""Measure Phase 5b rules against labels in the PostgreSQL dataset."""
import json
import os

import pandas as pd
import psycopg

from ml.features import TABLES, build_features

RULES = [
    "SURFACTURATION", "QUANTITE_EXCESSIVE", "UPCODING",
    "LIGNES_NON_PRESCRITES", "SUBSTITUTION_PRODUIT", "ORDONNANCE_EXPIREE",
    "SOINS_JOUR_FERME", "DOUBLON", "FRACTIONNEMENT", "SURCONSOMMATION",
    "ACTE_FICTIF", "INCOHERENCE_PROFIL", "PRESTATAIRE_RADIE", "HORS_COUVERTURE",
]


def frame(conn, table):
    cur = conn.execute(f"SELECT * FROM {table}")
    return pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])


def substitution_flags(tables):
    """Mapping: billed medication absent from prescription and not reimbursable."""
    f = tables["factures"][["facture_id", "ordonnance_id"]]
    billed = tables["lignes_facture"]
    billed = billed[billed["type_ligne"].eq("MEDICAMENT")].merge(f, on="facture_id")
    prescribed = tables["ordonnance_lignes"][["ordonnance_id", "code"]].drop_duplicates()
    meds = tables["referentiel_medicaments"][["code_medicament", "remboursable"]]
    billed = billed.merge(meds, left_on="code", right_on="code_medicament", how="left")
    billed = billed[billed["ordonnance_id"].notna()].merge(
        prescribed.assign(_prescribed=True), on=["ordonnance_id", "code"], how="left"
    )
    flagged = billed[~billed["_prescribed"].fillna(False) & billed["remboursable"].eq(False)]
    return flagged.groupby("facture_id").size().gt(0)


def upcoding_flags(tables):
    """Mapping: billed code differs from prescription and billed tariff is higher."""
    f = tables["factures"][["facture_id", "ordonnance_id"]]
    lines = tables["lignes_facture"].merge(f, on="facture_id")
    prescribed = tables["ordonnance_lignes"][["ordonnance_id", "code"]]
    acts = tables["referentiel_actes"][["code_acte", "tarif_reference"]].rename(
        columns={"code_acte": "code", "tarif_reference": "prescribed_price"}
    )
    meds = tables["referentiel_medicaments"][["code_medicament", "prix_reference"]].rename(
        columns={"code_medicament": "code", "prix_reference": "med_price"}
    )
    prescribed = prescribed.merge(acts, on="code", how="left").merge(meds, on="code", how="left")
    prescribed["prescribed_price"] = prescribed["prescribed_price"].fillna(prescribed["med_price"])
    max_price = prescribed.groupby("ordonnance_id")["prescribed_price"].max()
    codes = prescribed.groupby("ordonnance_id")["code"].apply(set)
    lines["max_prescribed_price"] = lines["ordonnance_id"].map(max_price)
    lines["prescribed_codes"] = lines["ordonnance_id"].map(codes)
    flagged = lines[
        lines["ordonnance_id"].notna()
        & lines["prescribed_codes"].map(lambda s: isinstance(s, set))
        & ~lines.apply(
            lambda r: isinstance(r["prescribed_codes"], set)
            and r["code"] in r["prescribed_codes"], axis=1
        )
        & (lines["prix_unitaire"] > lines["max_prescribed_price"])
    ]
    return flagged.groupby("facture_id").size().gt(0)


def main():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        tables = {name: frame(conn, name) for name in TABLES}
        labels = frame(conn, "labels_fraude")[["facture_id", "est_fraude", "type_fraude"]]
    X, _ = build_features(tables)
    flags = pd.DataFrame(index=X.index)
    flags["SURFACTURATION"] = X["l_n_sur_max"] > 0
    flags["QUANTITE_EXCESSIVE"] = X["l_q_ratio_max"] > 1.2
    flags["LIGNES_NON_PRESCRITES"] = X["l_n_hors_ordo"] > 0
    flags["SUBSTITUTION_PRODUIT"] = substitution_flags(tables).reindex(X.index, fill_value=False)
    flags["UPCODING"] = upcoding_flags(tables).reindex(X.index, fill_value=False)
    flags["ORDONNANCE_EXPIREE"] = X["ordo_exp_jours"] > 0
    flags["SOINS_JOUR_FERME"] = X["jour_ferme"] == 1
    flags["DOUBLON"] = (X["dup_numero"] > 1) & (X["dup_numero_rang"] > 0)
    flags["FRACTIONNEMENT"] = (X["meme_jour_n"] > 1) & (X["meme_jour_rang"] > 0)
    flags["SURCONSOMMATION"] = (X["ordo_n_factures"] > 1) & (X["ordo_rang_usage"] > 0)
    flags["ACTE_FICTIF"] = X["ordo_manquante_requise"] == 1
    flags["INCOHERENCE_PROFIL"] = (X["l_n_viol_age"] + X["l_n_viol_sexe"]) > 0
    flags["PRESTATAIRE_RADIE"] = X["jours_apres_fin_convention"] > 0
    flags["HORS_COUVERTURE"] = X["hors_periode_assure"].eq(1) | X["en_carence"].eq(1)

    joined = labels.set_index("facture_id").join(flags, how="inner")
    metrics = []
    for code in RULES:
        triggered = joined[code].fillna(False)
        labelled = joined["type_fraude"].eq(code)
        overlap = triggered & labelled
        metrics.append({
            "rule": code,
            "triggers": int(triggered.sum()),
            "labelled": int(labelled.sum()),
            "overlap": int(overlap.sum()),
            "recall": round(float(overlap.sum() / labelled.sum()), 6) if labelled.sum() else 0.0,
            "precision": round(float(overlap.sum() / triggered.sum()), 6) if triggered.sum() else 0.0,
        })

    type_map = {
        "MEDICAMENTS": {"PHARMACIE"}, "EXAMENS": {"LABORATOIRE", "IMAGERIE"},
        "KINE": {"KINESITHERAPIE"}, "OPTIQUE": {"OPTIQUE"},
    }
    ordos = tables["ordonnances"][["ordonnance_id", "type_ordonnance"]]
    facts = tables["factures"][["facture_id", "ordonnance_id", "type_facture"]].merge(
        ordos, on="ordonnance_id", how="left"
    )
    incoherent = facts["type_ordonnance"].notna() & facts.apply(
        lambda r: r["type_ordonnance"] in type_map and r["type_facture"] not in type_map[r["type_ordonnance"]], axis=1
    )
    incoherent.index = facts["facture_id"]
    explanatory = pd.DataFrame({
        "TYPE_ORDONNANCE_INCOHERENT": incoherent.reindex(flags.index, fill_value=False),
        "SPECIALITE_NON_DECLAREE": X["l_n_spec_mismatch"].fillna(0).gt(0),
    }).join(labels.set_index("facture_id")["est_fraude"])
    explanatory_rates = {
        code: {str(truth).lower(): round(float(explanatory.loc[explanatory.est_fraude.eq(truth), code].mean()), 6)
               for truth in (True, False)}
        for code in ("SPECIALITE_NON_DECLAREE", "TYPE_ORDONNANCE_INCOHERENT")
    }
    print(json.dumps({"metrics": metrics, "explanatory_rates": explanatory_rates}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
