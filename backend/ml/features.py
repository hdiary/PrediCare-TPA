"""Feature engineering P2 : détection de fraude sur les factures PrediCare TPA.

Entrée  : dictionnaire de DataFrames (CSV du jeu de données ou tables PostgreSQL).
Sortie  : un DataFrame indexé par facture_id, une ligne par facture.

Règles anti-fuite :
  * on n'utilise JAMAIS statut, motif_rejet, montant_pris_en_charge,
    reste_a_charge, date_traitement (décision historique) ;
  * on n'utilise JAMAIS labels_prestataires.est_suspect comme variable.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

TABLES = [
    "factures", "lignes_facture", "ordonnances", "ordonnance_lignes",
    "prestataires", "assures", "contrats", "referentiel_actes",
    "referentiel_medicaments", "grille_tarifaire", "garanties",
]

# Seules colonnes de `factures` autorisées (équivalent de v_factures_features).
ALLOWED_FACTURE_COLS = [
    "facture_id", "numero_facture", "prestataire_id", "assure_id", "contrat_id",
    "ordonnance_id", "type_facture", "date_soin", "heure_soin", "date_facture",
    "date_reception", "canal_reception", "mode_reglement", "attestation_pec_id",
    "entente_prealable_id", "devise", "nb_lignes", "montant_total",
    "montant_eligible",
]

CATEGORICAL = [
    "type_facture", "canal_reception", "mode_reglement", "type_prestataire",
    "specialite_prest", "niveau_tarif", "formule", "rang_beneficiaire",
    "type_ordonnance", "ordo_vs_facture",
]


def load_tables(dataset_dir: str | Path) -> dict[str, pd.DataFrame]:
    d = Path(dataset_dir)
    return {n: pd.read_csv(d / f"{n}.csv") for n in TABLES}


def _dates(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def build_features(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    f = t["factures"][ALLOWED_FACTURE_COLS].copy()
    _dates(f, ["date_soin", "date_facture", "date_reception"])
    hh = pd.to_datetime(f["heure_soin"], format="%H:%M", errors="coerce")
    f["heure"] = hh.dt.hour + hh.dt.minute / 60
    f["jour_semaine"] = (f["date_soin"].dt.weekday + 1)  # 1 = lundi ... 7 = dimanche
    f["mois_soin"] = f["date_soin"].dt.month

    pres = t["prestataires"].copy()
    _dates(pres, ["date_fin_convention", "date_conventionnement"])
    ass = t["assures"].copy()
    _dates(ass, ["date_adhesion", "date_radiation"])
    ctr = t["contrats"].copy()
    _dates(ctr, ["date_effet", "date_fin"])
    ordo = t["ordonnances"].copy()
    _dates(ordo, ["date_prescription"])
    gar = t["garanties"].copy()

    # ------------------------------------------------------------------ lignes
    actes = t["referentiel_actes"].rename(columns={"code_acte": "code"})
    meds = t["referentiel_medicaments"].rename(columns={"code_medicament": "code"})
    ref = pd.concat([
        actes[["code", "tarif_min", "tarif_reference", "tarif_max", "sexe_requis",
               "age_min", "age_max", "ordonnance_requise", "specialite"]],
        meds[["code", "prix_reference", "remboursable"]]
        .rename(columns={"prix_reference": "tarif_reference"}),
    ], ignore_index=True)

    L = t["lignes_facture"].merge(
        f[["facture_id", "prestataire_id", "assure_id", "ordonnance_id",
           "date_soin", "contrat_id", "type_facture"]], on="facture_id")
    L = L.merge(ref, on="code", how="left")
    L = L.merge(t["grille_tarifaire"], on=["prestataire_id", "code"], how="left")
    L = L.merge(ass[["assure_id", "sexe", "annee_naissance"]], on="assure_id", how="left")
    L = L.merge(pres[["prestataire_id", "specialite"]].rename(
        columns={"specialite": "specialite_prest"}), on="prestataire_id", how="left")

    L["r_max"] = L["prix_unitaire"] / L["tarif_max"]
    L["r_ref"] = L["prix_unitaire"] / L["tarif_reference"]
    L["r_grille"] = L["prix_unitaire"] / L["tarif_pratique"]
    L["sur_max"] = (L["prix_unitaire"] > L["tarif_max"]).astype(float)
    L.loc[L["tarif_max"].isna(), "sur_max"] = np.nan
    L["age"] = L["date_soin"].dt.year - L["annee_naissance"]
    L["viol_age"] = ((L["age"] < L["age_min"]) | (L["age"] > L["age_max"])).astype(float)
    L.loc[L["age_min"].isna(), "viol_age"] = np.nan
    L["viol_sexe"] = (L["sexe_requis"].notna() & (L["sexe_requis"] != L["sexe"])).astype(float)
    L["is_maj"] = L["code"].str.contains("MAJ|URG|NUIT", regex=True).astype(float)
    L["spec_mismatch"] = (L["specialite"].notna() & L["specialite_prest"].notna()
                          & (L["specialite"] != L["specialite_prest"])).astype(float)

    # rapprochement facture <-> ordonnance (même code prescrit ?)
    ol = t["ordonnance_lignes"][["ordonnance_id", "code", "quantite"]].rename(
        columns={"quantite": "qte_ord"}).groupby(["ordonnance_id", "code"], as_index=False).sum()
    L = L.merge(ol, on=["ordonnance_id", "code"], how="left")
    has_ord = L["ordonnance_id"].notna()
    L["hors_ordo"] = np.where(has_ord, L["qte_ord"].isna().astype(float), np.nan)
    L["q_ratio"] = L["quantite"] / L["qte_ord"]
    L["prix_hors_ordo"] = np.where(L["hors_ordo"] == 1, L["prix_unitaire"], 0)

    # actes exclus par la formule du contrat
    excl = gar[["formule", "categorie", "actes_exclus"]].dropna().copy()
    excl["code"] = excl["actes_exclus"].str.split("|")
    excl = excl.explode("code")[["formule", "categorie", "code"]].assign(exclu=1.0)
    L = L.merge(ctr[["contrat_id", "formule"]], on="contrat_id", how="left")
    L = L.merge(excl, left_on=["formule", "type_facture", "code"],
                right_on=["formule", "categorie", "code"], how="left")
    L["exclu"] = L["exclu"].fillna(0.0)

    agg = L.groupby("facture_id").agg(
        l_r_max=("r_max", "max"), l_r_ref_max=("r_ref", "max"),
        l_r_ref_min=("r_ref", "min"), l_r_grille_max=("r_grille", "max"),
        l_n_sur_max=("sur_max", "sum"), l_qte_max=("quantite", "max"),
        l_q_ratio_max=("q_ratio", "max"), l_n_hors_ordo=("hors_ordo", "sum"),
        l_part_hors_ordo=("hors_ordo", "mean"), l_prix_hors_ordo_max=("prix_hors_ordo", "max"),
        l_n_viol_age=("viol_age", "sum"), l_n_viol_sexe=("viol_sexe", "sum"),
        l_n_maj=("is_maj", "sum"), l_n_spec_mismatch=("spec_mismatch", "sum"),
        l_n_exclu=("exclu", "sum"), l_ordo_requise=("ordonnance_requise", "max"),
        l_n_non_remboursable=("remboursable", lambda s: (s == 0).sum()),
        l_n_codes_distincts=("code", "nunique"),
    ).reset_index()
    f = f.merge(agg, on="facture_id", how="left")

    # ------------------------------------------------------------- ordonnance
    f = f.merge(
        ordo[["ordonnance_id", "assure_id", "prescripteur_id", "date_prescription",
              "validite_jours", "type_ordonnance"]].rename(columns={"assure_id": "assure_ordo"}),
        on="ordonnance_id", how="left")
    f["a_ordonnance"] = f["ordonnance_id"].notna().astype(int)
    f["delai_ordo_soin"] = (f["date_soin"] - f["date_prescription"]).dt.days
    f["ordo_exp_jours"] = f["delai_ordo_soin"] - f["validite_jours"]
    f["ordo_autre_assure"] = np.where(
        f["ordonnance_id"].notna(), (f["assure_ordo"] != f["assure_id"]).astype(float), np.nan)
    f["ordo_vs_facture"] = (f["type_ordonnance"].fillna("AUCUNE") + ">" + f["type_facture"])
    f["ordo_manquante_requise"] = ((f["ordonnance_id"].isna()) & (f["l_ordo_requise"] == 1)).astype(int)
    g = f.groupby("ordonnance_id")
    f["ordo_n_factures"] = g["facture_id"].transform("size")
    f["ordo_n_prestataires"] = g["prestataire_id"].transform("nunique")
    f.loc[f["ordonnance_id"].isna(), ["ordo_n_factures", "ordo_n_prestataires"]] = np.nan

    # ------------------------------------------------------ doublons / volume
    f["dup_numero"] = f.groupby("numero_facture")["facture_id"].transform("size")
    k = ["assure_id", "prestataire_id", "montant_total", "date_soin"]
    f["dup_cle"] = f.groupby(k)["facture_id"].transform("size")
    k2 = ["assure_id", "prestataire_id", "date_soin"]
    f["meme_jour_n"] = f.groupby(k2)["facture_id"].transform("size")
    f["meme_jour_somme"] = f.groupby(k2)["montant_total"].transform("sum")
    # rang dans le groupe : seul l'exemplaire renvoyé est la fraude, pas l'original
    f = f.sort_values(["date_soin", "facture_id"])
    f["dup_cle_rang"] = f.groupby(k).cumcount()
    f["dup_numero_rang"] = f.groupby("numero_facture").cumcount()
    f["meme_jour_rang"] = f.groupby(k2).cumcount()
    f["meme_jour_montant_cumule"] = f.groupby(k2)["montant_total"].cumsum() - f["montant_total"]
    f["ordo_rang_usage"] = f.groupby("ordonnance_id").cumcount()
    f.loc[f["ordonnance_id"].isna(), "ordo_rang_usage"] = np.nan
    f["assure_mois_n"] = f.groupby(["assure_id", f["date_soin"].dt.to_period("M")])["facture_id"].transform("size")
    f["assure_n_total"] = f.groupby("assure_id")["facture_id"].transform("size")
    f["prest_n_factures"] = f.groupby("prestataire_id")["facture_id"].transform("size")
    f["prest_montant_moy"] = f.groupby("prestataire_id")["montant_total"].transform("mean")
    f["prest_jour_n"] = f.groupby(["prestataire_id", "date_soin"])["facture_id"].transform("size")

    # -------------------------------------------------------------- prestataire
    f = f.merge(
        pres[["prestataire_id", "type_prestataire", "specialite", "niveau_tarif",
              "note_qualite", "conventionne", "statut", "jours_ouverture",
              "heure_ouverture", "heure_fermeture", "date_fin_convention",
              "date_conventionnement"]].rename(
            columns={"specialite": "specialite_prest", "statut": "statut_prest"}),
        on="prestataire_id", how="left")
    f["jour_ferme"] = [
        float(str(d) not in str(j)) if pd.notna(j) else np.nan
        for d, j in zip(f["jour_semaine"], f["jours_ouverture"])]
    f["hors_horaires"] = ((f["heure"] < f["heure_ouverture"]) | (f["heure"] >= f["heure_fermeture"])).astype(float)
    f["jours_apres_fin_convention"] = (f["date_soin"] - f["date_fin_convention"]).dt.days
    f["jours_depuis_convention"] = (f["date_soin"] - f["date_conventionnement"]).dt.days
    f["prest_radie"] = (f["statut_prest"] == "RADIE").astype(int)

    # ------------------------------------------------------ assuré / contrat
    f = f.merge(ass[["assure_id", "rang_beneficiaire", "sexe", "annee_naissance",
                     "date_adhesion", "date_radiation"]], on="assure_id", how="left")
    f = f.merge(ctr[["contrat_id", "formule", "date_effet", "date_fin"]], on="contrat_id", how="left")
    f = f.merge(gar[["formule", "categorie", "delai_carence_jours", "taux_remboursement",
                     "plafond_annuel_categorie", "franchise_par_facture"]].rename(
        columns={"categorie": "type_facture"}), on=["formule", "type_facture"], how="left")
    f["age_assure"] = f["date_soin"].dt.year - f["annee_naissance"]
    f["jours_depuis_adhesion"] = (f["date_soin"] - f["date_adhesion"]).dt.days
    f["jours_avant_radiation"] = (f["date_radiation"] - f["date_soin"]).dt.days
    f["gap_carence"] = f["delai_carence_jours"] - f["jours_depuis_adhesion"]
    f["jours_depuis_effet"] = (f["date_soin"] - f["date_effet"]).dt.days
    f["jours_avant_fin_contrat"] = (f["date_fin"] - f["date_soin"]).dt.days

    # ---------------------------------------------------------------- base
    f["delai_soin_facture"] = (f["date_facture"] - f["date_soin"]).dt.days
    f["delai_facture_reception"] = (f["date_reception"] - f["date_facture"]).dt.days
    f["ratio_eligible"] = f["montant_eligible"] / f["montant_total"].replace(0, np.nan)
    f["montant_par_ligne"] = f["montant_total"] / f["nb_lignes"]
    f["a_attestation"] = f["attestation_pec_id"].notna().astype(int)
    f["a_entente"] = f["entente_prealable_id"].notna().astype(int)
    f["ratio_vs_prest_moy"] = f["montant_total"] / f["prest_montant_moy"]

    drop = ["numero_facture", "prestataire_id", "assure_id", "contrat_id", "ordonnance_id",
            "date_soin", "heure_soin", "date_facture", "date_reception", "attestation_pec_id",
            "entente_prealable_id", "devise", "assure_ordo", "prescripteur_id",
            "date_prescription", "statut_prest", "jours_ouverture", "date_fin_convention",
            "date_conventionnement", "sexe", "annee_naissance", "date_adhesion",
            "date_radiation", "date_effet", "date_fin"]
    meta = f[["facture_id", "assure_id", "prestataire_id", "date_soin"]].copy()
    X = f.drop(columns=drop).set_index("facture_id")
    for c in CATEGORICAL:
        X[c] = X[c].astype("category")
    meta = meta.set_index("facture_id")
    return X, meta
