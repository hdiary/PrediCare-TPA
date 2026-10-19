"""Règles de détection des anomalies de PRESCRIPTION (P2-12).

Le cahier des charges demande de « détecter et alerter sur les anomalies de
prescriptions (doublons, inadéquation prescription/maladie...) ». Les labels du jeu
de données ne couvrent que les factures : ces contrôles sont donc des RÈGLES
explicables, complémentaires au modèle ML, qui travaillent sur `ordonnances`.

Règles (code = celui du Référentiel métier quand il existe) :
  ORDONNANCE_ANTIDATEE        prescription avant l'adhésion du bénéficiaire
  PRESCRIPTEUR_RADIE          prescripteur déconventionné à la date, ou n° ONM
                              absent/invalide pour un médecin
  DOUBLON_PRESCRIPTION        mêmes lignes prescrites au même assuré sous 3 jours
  INADEQUATION_DIAGNOSTIC     médicament/acte jamais prescrit pour ce diagnostic
  PRESCRIPTEUR_INCOMPATIBLE   diagnostic hors du champ habituel de la spécialité
  ORDONNANCE_FALSIFIEE        quantité ou durée au-delà du maximum observé

Les règles « apprises » (INADEQUATION, INCOMPATIBLE, FALSIFIEE) comparent à un
historique de référence (`fit_reference`) : à recalculer sur la base à jour.

    ref = fit_reference(tables)
    alertes = check_ordonnances(tables, ref)   # une ligne par (ordonnance, règle)
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

DOUBLON_JOURS = 3          # fenêtre de doublon de prescription
MIN_PART_DIAG_CODE = 0.005  # part min d'un code dans un diagnostic pour être « normal »
MIN_PART_SPEC_DIAG = 0.005  # part min d'un diagnostic dans une spécialité
MIN_EFFECTIF = 200          # historique minimal pour juger une spécialité
ONM_RE = re.compile(r"^ONM-\d{5}$")
TYPES_MEDECIN = {"CABINET_GENERALISTE", "CABINET_SPECIALISTE", "MATERNITE"}
GRAVITE = {  # 1 = à vérifier, 2 = suspect, 3 = grave
    "ORDONNANCE_ANTIDATEE": 3, "PRESCRIPTEUR_RADIE": 3, "ORDONNANCE_FALSIFIEE": 3,
    "DOUBLON_PRESCRIPTION": 2, "PRESCRIPTEUR_INCOMPATIBLE": 2, "INADEQUATION_DIAGNOSTIC": 2,
}
COLS = ["ordonnance_id", "regle", "gravite", "detail"]


def _duree(posologie: pd.Series) -> pd.Series:
    return posologie.str.extract(r"pendant (\d+) jours")[0].astype(float)


def _prescripteurs(t: dict) -> pd.DataFrame:
    o = t["ordonnances"].copy()
    o["date_prescription"] = pd.to_datetime(o["date_prescription"], errors="coerce")
    p = t["prestataires"].copy()
    p["date_fin_convention"] = pd.to_datetime(p["date_fin_convention"], errors="coerce")
    p = p[["prestataire_id", "type_prestataire", "specialite", "statut",
           "numero_onm", "date_fin_convention"]]
    return o.merge(p, left_on="prescripteur_id", right_on="prestataire_id", how="left")


def fit_reference(t: dict) -> dict:
    """Apprend ce qui est « normal » dans l'historique (à refaire quand la base évolue)."""
    o = _prescripteurs(t)
    ol = t["ordonnance_lignes"].merge(o[["ordonnance_id", "diagnostic"]], on="ordonnance_id")
    part = (ol.dropna(subset=["diagnostic"]).groupby(["diagnostic", "code"]).size()
            / ol.dropna(subset=["diagnostic"]).groupby("diagnostic").size())
    diag_code = set(part[part >= MIN_PART_DIAG_CODE].index)

    od = o.dropna(subset=["diagnostic", "specialite"])
    eff = od.groupby("specialite").size()
    ps = od.groupby(["specialite", "diagnostic"]).size().div(eff, level="specialite")
    spec_diag = set(ps[ps >= MIN_PART_SPEC_DIAG].index)
    specs_ok = set(eff[eff >= MIN_EFFECTIF].index)

    return {
        "diag_code": diag_code, "spec_diag": spec_diag, "specs_jugees": specs_ok,
        "qte_max": ol.groupby("code")["quantite"].max().to_dict(),
        "duree_max": float(_duree(t["ordonnance_lignes"]["posologie"]).max()),
    }


def check_ordonnances(t: dict, ref: dict | None = None) -> pd.DataFrame:
    """Retourne les alertes : colonnes ordonnance_id, regle, gravite, detail."""
    ref = ref or fit_reference(t)
    o = _prescripteurs(t)
    ass = t["assures"][["assure_id", "date_adhesion"]].copy()
    ass["date_adhesion"] = pd.to_datetime(ass["date_adhesion"], errors="coerce")
    o = o.merge(ass, on="assure_id", how="left")
    ol = t["ordonnance_lignes"].copy()
    out: list[pd.DataFrame] = []

    def add(mask_df: pd.DataFrame, regle: str, detail) -> None:
        if len(mask_df):
            d = pd.DataFrame({"ordonnance_id": mask_df["ordonnance_id"].values,
                              "regle": regle, "gravite": GRAVITE[regle],
                              "detail": detail(mask_df) if callable(detail) else detail})
            out.append(d)

    # 1. antidatée
    m = o[o["date_prescription"] < o["date_adhesion"]]
    add(m, "ORDONNANCE_ANTIDATEE", lambda d: [
        f"prescrite le {a:%Y-%m-%d}, avant l'adhésion du {b:%Y-%m-%d}"
        for a, b in zip(d["date_prescription"], d["date_adhesion"])])

    # 2. prescripteur radié / inconnu / ONM invalide
    radie = (o["statut"] == "RADIE") & (o["date_prescription"] > o["date_fin_convention"])
    inconnu = o["prestataire_id"].isna()
    onm_ko = o["type_prestataire"].isin(TYPES_MEDECIN) & ~o["numero_onm"].fillna("").str.match(ONM_RE)
    m = o[radie | inconnu | onm_ko]
    add(m, "PRESCRIPTEUR_RADIE", lambda d: np.select(
        [d["prestataire_id"].isna(), d["statut"] == "RADIE"],
        ["prescripteur absent du référentiel",
         "prescripteur déconventionné à la date de prescription"],
        "numéro ONM absent ou invalide"))

    # 3. doublons de prescription
    sig = ol.sort_values("code").groupby("ordonnance_id")["code"].apply("|".join).rename("sig")
    d = o.join(sig, on="ordonnance_id").sort_values(["assure_id", "sig", "date_prescription"])
    g = d.groupby(["assure_id", "sig"])
    d["gap"] = g["date_prescription"].diff().dt.days
    d["presc_prec"] = g["prescripteur_id"].shift()
    m = d[d["gap"] <= DOUBLON_JOURS]
    add(m, "DOUBLON_PRESCRIPTION", lambda x: [
        f"mêmes lignes déjà prescrites il y a {int(a)} j ("
        + ("même" if s == p else "autre") + " prescripteur)"
        for a, s, p in zip(x["gap"], x["prescripteur_id"], x["presc_prec"])])

    # 4. inadéquation diagnostic / lignes
    L = ol.merge(o[["ordonnance_id", "diagnostic"]], on="ordonnance_id")
    L = L[L["diagnostic"].notna()]
    L = L[[(dg, c) not in ref["diag_code"] for dg, c in zip(L["diagnostic"], L["code"])]]
    if len(L):
        agg = L.groupby("ordonnance_id").agg(diag=("diagnostic", "first"), codes=("code", lambda s: ", ".join(s)))
        add(agg.reset_index(), "INADEQUATION_DIAGNOSTIC", lambda x: [
            f"{c} jamais prescrit pour « {dg} »" for c, dg in zip(x["codes"], x["diag"])])

    # 5. prescripteur hors champ de compétence
    s = o[o["specialite"].isin(ref["specs_jugees"]) & o["diagnostic"].notna()]
    m = s[[(sp, dg) not in ref["spec_diag"] for sp, dg in zip(s["specialite"], s["diagnostic"])]]
    add(m, "PRESCRIPTEUR_INCOMPATIBLE", lambda x: [
        f"{sp} : « {dg} » hors de son champ habituel"
        for sp, dg in zip(x["specialite"], x["diagnostic"])])

    # 6. quantité / durée surchargée
    ol["qmax"] = ol["code"].map(ref["qte_max"])
    ol["duree"] = _duree(ol["posologie"])
    bad = ol[(ol["quantite"] > ol["qmax"]) | (ol["duree"] > ref["duree_max"])]
    if len(bad):
        add(bad.drop_duplicates("ordonnance_id"), "ORDONNANCE_FALSIFIEE", lambda x: [
            f"{c} : quantité {q:g} (max observé {qm:g})" if q > qm else f"{c} : durée {du:g} j (max {ref['duree_max']:g})"
            for c, q, qm, du in zip(x["code"], x["quantite"], x["qmax"], x["duree"])])

    res = pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=COLS)
    return res[COLS].sort_values(["gravite", "ordonnance_id"], ascending=[False, True]).reset_index(drop=True)


def resume_par_ordonnance(alertes: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par ordonnance : gravité max, règles déclenchées."""
    return alertes.groupby("ordonnance_id").agg(
        gravite=("gravite", "max"), regles=("regle", lambda s: ", ".join(sorted(set(s)))),
        nb_regles=("regle", "nunique")).reset_index()
