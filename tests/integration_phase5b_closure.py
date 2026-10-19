import json
import os

import pandas as pd
import psycopg

from ml.features import TABLES, build_features
from tests.integration_fraud_rates import substitution_flags, upcoding_flags


def frame(conn, table):
    cur = conn.execute(f"SELECT * FROM {table}")
    return pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])


def main():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        t = {name: frame(conn, name) for name in TABLES}
        labels = frame(conn, "labels_fraude")
    X, _ = build_features(t)
    joined = labels.set_index("facture_id").join(X, how="inner")

    examples = {}
    for code in ("UPCODING", "SUBSTITUTION_PRODUIT"):
        rows = labels[labels.type_fraude.eq(code)].head(10)
        examples[code] = []
        for _, row in rows.iterrows():
            fid = row.facture_id
            lines = t["lignes_facture"][t["lignes_facture"].facture_id.eq(fid)]
            ord_id = t["factures"].set_index("facture_id").at[fid, "ordonnance_id"]
            prescribed = t["ordonnance_lignes"][t["ordonnance_lignes"].ordonnance_id.eq(ord_id)]
            examples[code].append({
                "facture_id": fid,
                "detail_fraude": row.detail_fraude,
                "ordonnance_id": ord_id,
                "facture_lines": lines[["code", "type_ligne", "prix_unitaire"]].to_dict("records"),
                "prescribed_lines": prescribed[["code", "quantite"]].to_dict("records"),
                "rule_triggered": bool(joined.at[fid, "l_n_non_remboursable"] > 0) if code == "SUBSTITUTION_PRODUIT" else bool(upcoding_flags(t).reindex([fid], fill_value=False).iloc[0]),
            })

    f = t["factures"][["facture_id", "numero_facture", "date_facture", "date_soin"]].copy()
    labels_i = labels.set_index("facture_id")
    f["dup_date"] = f.sort_values(["numero_facture", "date_facture", "facture_id"]).groupby("numero_facture").cumcount().reindex(f.index).fillna(0)
    f["dup_id"] = f.sort_values(["numero_facture", "facture_id"]).groupby("numero_facture").cumcount().reindex(f.index).fillna(0)
    duplicate_metrics = {}
    for name in ("dup_date", "dup_id"):
        triggered = f[name] > 0
        typed = labels_i.type_fraude.eq("DOUBLON").reindex(f.facture_id).fillna(False).to_numpy()
        overlap = (triggered.to_numpy() & typed).sum()
        nlabel = typed.sum()
        duplicate_metrics[name] = {"triggers": int(triggered.sum()), "overlap": int(overlap), "recall": float(overlap / nlabel)}

    lines = t["lignes_facture"].merge(t["factures"][["facture_id", "prestataire_id", "date_soin"]], on="facture_id")
    lines = lines.merge(t["referentiel_actes"][["code_acte", "tarif_max"]].rename(columns={"code_acte": "code"}), on="code", how="left")
    lines["max"] = lines["tarif_max"]
    threshold_metrics = {}
    for factor in (1.0, 1.2):
        trigger_ids = set(lines.loc[lines["max"].notna() & (lines.prix_unitaire > factor * lines["max"]), "facture_id"])
        typed = labels.type_fraude.eq("SURFACTURATION")
        overlap = labels.facture_id.isin(trigger_ids) & typed
        threshold_metrics[str(factor)] = {"triggers": len(trigger_ids), "overlap": int(overlap.sum()), "labels": int(typed.sum()), "recall": float(overlap.sum() / typed.sum()), "precision": float(overlap.sum() / len(trigger_ids))}

    p = t["prestataires"][["prestataire_id", "date_fin_convention", "statut"]]
    post = t["factures"][["facture_id", "prestataire_id", "date_soin"]].merge(p, on="prestataire_id")
    post["trigger"] = post.date_fin_convention.notna() & (post.date_soin > post.date_fin_convention)
    trigger_ids = set(post.loc[post.trigger, "facture_id"])
    typed = labels.type_fraude.eq("PRESTATAIRE_RADIE")
    overlap = labels.facture_id.isin(trigger_ids) & typed
    post_metrics = {"triggers": len(trigger_ids), "overlap": int(overlap.sum()), "labels": int(typed.sum()), "recall": float(overlap.sum() / typed.sum()), "precision": float(overlap.sum() / len(trigger_ids))}
    print(json.dumps({"examples": examples, "duplicate": duplicate_metrics, "surcharge": threshold_metrics, "prestataire_radie_post_fin_convention": post_metrics}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
