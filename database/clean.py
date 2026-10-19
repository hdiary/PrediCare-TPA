#!/usr/bin/env python3
"""
clean.py - PrediCare TPA (P1): typing, validation, rejects and Parquet export.

Implements the data contract v0.1 (CohorteAI_datagen/dataset).

What it does
------------
1. Reads every CSV as text (nothing is guessed by pandas: ids, nif, numero_cin
   and jours_ouverture stay strings).
2. Casts each column to its contract type (BIGINT, SMALLINT, BOOLEAN, DATE,
   TIME, TEXT[]), checks formats, enums, ranges and foreign keys.
3. Rejects invalid rows into <rejets>/<table>.csv with a readable reason
   (invoice rejects use the 10 official invalidity codes).
4. Splits personal data: identites_pii.csv goes to <secure>/ only. Its rejects
   never contain personal values, only assure_id + reason.
5. Writes one Parquet file per table to <out>/, plus ref_codes.parquet and
   factures_features.parquet (leak columns removed, for P2).
6. Writes <out>/_manifest.json (input SHA-256, row counts, reject counts) that
   load.py can reuse for ingestion_log.

What it does NOT do (on purpose)
--------------------------------
- It never "fixes" suspicious business content: repeated numero_facture,
  re-used ordonnance_id, prices above the maximum tariff, closed-day care...
  These are the injected frauds P2 must detect. Only form is cleaned.
- It does not encrypt: encryption (Fernet) happens in the loading step, from
  <secure>/identites_pii.parquet. Delete that file once encrypted and keep
  <secure>/ out of Git.

Idempotent: same inputs + same --today => same outputs.

Usage
-----
python clean.py --src dataset --out data/clean --rejets data/rejets \
                --secure data/secure [--labels labels] [--today 2026-10-14]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# --------------------------------------------------------------------------- #
# Constants from the contract
# --------------------------------------------------------------------------- #
PII_COLS = {"nom", "prenoms", "date_naissance", "telephone", "email",
            "adresse", "numero_cin"}
LEAK_COLS = ["montant_pris_en_charge", "reste_a_charge", "statut",
             "motif_rejet", "date_traitement"]
FORMULES = ["ESSENTIEL", "CONFORT", "PREMIUM"]
CATEGORIES = ["CONSULTATION", "PHARMACIE", "LABORATOIRE", "IMAGERIE",
              "DENTAIRE", "KINESITHERAPIE", "MATERNITE", "OPTIQUE",
              "HOSPITALISATION"]
FRAUD_TYPES = ["SURFACTURATION", "QUANTITE_EXCESSIVE", "UPCODING",
               "LIGNES_NON_PRESCRITES", "SUBSTITUTION_PRODUIT",
               "ORDONNANCE_EXPIREE", "SOINS_JOUR_FERME", "DOUBLON",
               "FRACTIONNEMENT", "SURCONSOMMATION", "ACTE_FICTIF",
               "INCOHERENCE_PROFIL", "PRESTATAIRE_RADIE", "HORS_COUVERTURE"]
INVALID_CODES = ["MONTANT_NEGATIF", "CODE_ACTE_INCONNU", "DATE_FUTURE",
                 "DATE_IMPOSSIBLE", "CHAMP_OBLIGATOIRE_MANQUANT",
                 "TOTAL_INCOHERENT", "PRESTATAIRE_INCONNU", "ASSURE_INCONNU",
                 "DEVISE_INVALIDE", "FACTURE_SANS_LIGNE"]
TRUE_VALUES = {"1", "true", "t", "yes", "y", "oui", "o"}
FALSE_VALUES = {"0", "false", "f", "no", "n", "non"}

RX = {
    "ASS": r"^ASS-[0-9A-F]{10}$",
    "CTR": r"^CTR-\d{6}$",
    "PRE": r"^PRE-\d{5}$",
    "FAC": r"^FAC-\d{8}$",
    "ORD": r"^ORD-\d{7}$",
    "SOU": r"^SOU-(\d{4}|IND)$",  # SOU-IND = individual (non-group) policies
    "LIG": r"^FAC-\d{8}-L\d{2}$",
    "TEL": r"^0\d{2} \d{2} \d{3} \d{2}$",
    "MAIL": r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
}

ARROW = {"str": pa.string(), "i16": pa.int16(), "i64": pa.int64(),
         "bool": pa.bool_(), "date": pa.date32(), "time": pa.time32("s"),
         "arr": pa.list_(pa.string())}


# --------------------------------------------------------------------------- #
# Casting helpers
# --------------------------------------------------------------------------- #
def cast(s: pd.Series, kind: str) -> tuple[pd.Series, pd.Series]:
    """Return (typed series, mask of values present but not parsable)."""
    s = s.astype("string").str.strip()
    s = s.mask((s == "").fillna(False))
    present = s.notna()
    no_bad = pd.Series(False, index=s.index)

    if kind == "str":
        return s, no_bad

    if kind in ("i16", "i64"):
        num = pd.to_numeric(s, errors="coerce")
        limit = 32767 if kind == "i16" else 2 ** 53
        ok = (num.notna() & (num % 1 == 0) & (num.abs() <= limit))
        ok = ok.fillna(False).astype(bool)
        return num.where(ok).astype("Int64"), present & ~ok

    if kind == "bool":
        low = s.str.lower()
        is_t, is_f = low.isin(TRUE_VALUES), low.isin(FALSE_VALUES)
        val = pd.Series(pd.NA, index=s.index, dtype="boolean")
        val[is_t] = True
        val[is_f] = False
        return val, present & ~(is_t | is_f)

    if kind == "date":
        fmt = s.str.fullmatch(r"\d{4}-\d{2}-\d{2}").fillna(False).astype(bool)
        d = pd.to_datetime(s.where(fmt), format="%Y-%m-%d", errors="coerce")
        return d, present & d.isna()

    if kind == "time":
        ok = s.str.fullmatch(r"([01]\d|2[0-3]):[0-5]\d").fillna(False)
        ok = ok.astype(bool)
        return s.where(ok), present & ~ok

    if kind == "arr":  # 'A|B|C' -> ['A', 'B', 'C']
        def split(x):
            if pd.isna(x):
                return None
            parts = [p.strip() for p in x.split("|") if p.strip()]
            return parts or None
        return s.map(split).astype(object), no_bad

    raise ValueError(f"unknown kind {kind}")


def to_arrow(df: pd.DataFrame, cols: dict[str, str]) -> pa.Table:
    arrays = []
    for col, kind in cols.items():
        s = df[col]
        if kind == "arr":
            vals = [x if isinstance(x, list) else None for x in s]
        elif kind == "date":
            vals = [None if pd.isna(x) else x.date() for x in s]
        elif kind == "time":
            vals = [None if pd.isna(x) else dt.time(int(x[:2]), int(x[3:5]))
                    for x in s]
        elif kind in ("i16", "i64"):
            vals = [None if pd.isna(x) else int(x) for x in s]
        elif kind == "bool":
            vals = [None if pd.isna(x) else bool(x) for x in s]
        else:
            vals = [None if pd.isna(x) else str(x) for x in s]
        arrays.append(pa.array(vals, type=ARROW[kind]))
    return pa.Table.from_arrays(arrays, names=list(cols))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# Check helpers (each returns a boolean mask: True = row is bad)
# --------------------------------------------------------------------------- #
def en(df, col, values):
    """Value present but outside the allowed list."""
    return df[col].notna() & ~df[col].isin(list(values))


def lt(df, col, bound):
    return df[col] < bound


# --------------------------------------------------------------------------- #
# Table specifications
# --------------------------------------------------------------------------- #
def spec(pk, cols, null=(), regex=None, fks=(), checks=None, warns=None,
         file=None, sensitive=False, labels=False):
    return dict(pk=pk if isinstance(pk, list) else [pk], cols=cols,
                null=set(null), regex=regex or {}, fks=list(fks),
                checks=checks, warns=warns, file=file, sensitive=sensitive,
                labels=labels)


def chk_actes(df, ctx):
    return [
        ("TARIFS_INCOHERENTS", (df.tarif_min > df.tarif_reference)
         | (df.tarif_reference > df.tarif_max) | (df.tarif_min < 0)),
        ("VALEUR_INTERDITE:sexe_requis", en(df, "sexe_requis", ["F", "M"])),
        ("AGE_INCOHERENT", df.age_min > df.age_max),
    ]


def chk_meds(df, ctx):
    return [("MONTANT_NEGATIF", df.prix_reference < 0)]


def chk_garanties(df, ctx):
    return [
        ("VALEUR_INTERDITE:formule", en(df, "formule", FORMULES)),
        ("VALEUR_INTERDITE:categorie", en(df, "categorie", CATEGORIES)),
        ("TAUX_HORS_BORNES", (df.taux_remboursement < 0)
         | (df.taux_remboursement > 100)),
        ("MONTANT_NEGATIF", (df.plafond_annuel_categorie < 0)
         | (df.franchise_par_facture < 0) | (df.plafond_annuel_global < 0)
         | (df.prime_annuelle_par_beneficiaire < 0)),
        ("CARENCE_NEGATIVE", df.delai_carence_jours < 0),
    ]


def chk_prestataires(df, ctx):
    return [
        ("HEURE_HORS_BORNES", (df.heure_ouverture < 0)
         | (df.heure_ouverture > 24) | (df.heure_fermeture < 0)
         | (df.heure_fermeture > 24)),
        ("NOTE_HORS_BORNES", (df.note_qualite < 1) | (df.note_qualite > 5)),
        ("VALEUR_INTERDITE:statut", en(df, "statut", ["ACTIF", "RADIE"])),
        ("VALEUR_INTERDITE:niveau_tarif",
         en(df, "niveau_tarif", ["RAISONNABLE", "ELEVE", "TRES_ELEVE"])),
        ("CONVENTION_INCOHERENTE", df.date_fin_convention
         < df.date_conventionnement),
    ]


def chk_grille(df, ctx):
    return [
        ("CODE_ACTE_INCONNU", df.code.notna()
         & ~df.code.isin(ctx.keys["ref_codes"])),
        ("MONTANT_NEGATIF", df.tarif_pratique < 0),
    ]


def chk_contrats(df, ctx):
    return [
        ("VALEUR_INTERDITE:formule", en(df, "formule", FORMULES)),
        ("VALEUR_INTERDITE:statut", en(df, "statut", ["ACTIF", "RESILIE"])),
        ("STATUT_DATE_FIN_INCOHERENT",
         (df.statut == "RESILIE") != df.date_fin.notna()),
        ("DATES_INCOHERENTES", df.date_fin < df.date_effet),
        ("NB_BENEFICIAIRES_INVALIDE", df.nb_beneficiaires < 1),
        ("MONTANT_NEGATIF", df.prime_annuelle_totale < 0),
    ]


def chk_assures(df, ctx):
    return [
        ("VALEUR_INTERDITE:sexe", en(df, "sexe", ["M", "F"])),
        ("VALEUR_INTERDITE:rang_beneficiaire", en(
            df, "rang_beneficiaire", ["ASSURE_PRINCIPAL", "CONJOINT",
                                      "ENFANT"])),
        ("PRINCIPAL_INCONNU", df.assure_principal_id.notna()
         & ~df.assure_principal_id.isin(df.assure_id)),
        ("PRINCIPAL_INCOHERENT", (df.rang_beneficiaire == "ASSURE_PRINCIPAL")
         & (df.assure_principal_id != df.assure_id)),
        ("DATES_INCOHERENTES", df.date_radiation < df.date_adhesion),
        ("ANNEE_NAISSANCE_INVALIDE", (df.annee_naissance < 1900)
         | (df.annee_naissance > ctx.today.year)),
    ]


def chk_identites(df, ctx):
    a = ctx.kept["assures"].set_index("assure_id")
    ann = pd.to_numeric(df.assure_id.map(a["annee_naissance"]),
                        errors="coerce")
    year = df.date_naissance.dt.year.astype("float64")
    return [
        ("INCOHERENT_AVEC_ASSURES:annee_naissance", ann != year),
        ("INCOHERENT_AVEC_ASSURES:sexe",
         df.assure_id.map(a["sexe"]).astype("string") != df.sexe),
        ("INCOHERENT_AVEC_ASSURES:ville",
         df.assure_id.map(a["ville"]).astype("string") != df.ville),
    ]


def chk_ordonnances(df, ctx):
    return [
        ("VALIDITE_INVALIDE", df.validite_jours < 1),
        ("VALEUR_INTERDITE:type_ordonnance", en(
            df, "type_ordonnance", ["MEDICAMENTS", "EXAMENS", "KINE",
                                    "OPTIQUE"])),
        ("DIAGNOSTIC_CLINIQUE_INCOHERENT",
         df.diagnostic.isna() != df.renseignement_clinique.isna()),
    ]


def chk_ord_lignes(df, ctx):
    return [
        ("CODE_ACTE_INCONNU", df.code.notna()
         & ~df.code.isin(ctx.keys["ref_codes"])),
        ("MONTANT_NEGATIF", (df.quantite <= 0) | (df.num_ligne < 1)),
    ]


def chk_lignes(df, ctx):
    return [
        ("MONTANT_NEGATIF", (df.quantite <= 0) | (df.prix_unitaire < 0)
         | (df.montant < 0)),
        ("CODE_ACTE_INCONNU", df.code.notna()
         & ~df.code.isin(ctx.keys["ref_codes"])),
        ("MONTANT_LIGNE_INCOHERENT",
         df.montant != df.quantite * df.prix_unitaire),
        ("VALEUR_INTERDITE:type_ligne", en(df, "type_ligne",
                                           ["ACTE", "MEDICAMENT"])),
        ("NUM_LIGNE_INVALIDE", df.num_ligne < 1),
        ("LIGNE_DUPLIQUEE", df.duplicated(["facture_id", "num_ligne"],
                                          keep="first")),
    ]


def warn_lignes(df, ctx):
    is_act = df.code.isin(ctx.keys["codes_actes"])
    is_med = df.code.isin(ctx.keys["codes_meds"])
    return [("TYPE_LIGNE_INCOHERENT_AVEC_REFERENTIEL",
             ((df.type_ligne == "ACTE") & ~is_act)
             | ((df.type_ligne == "MEDICAMENT") & ~is_med))]


def chk_factures(df, ctx):
    L = ctx.state["lignes_facture"]
    ldf, lrs = L["df"], L["reasons"]
    ids = df.facture_id
    n_lines = ldf.groupby("facture_id").size().astype("float64")
    sum_m = ldf.groupby("facture_id")["montant"].sum().astype("float64")

    def lines_with(motif):
        return set(ldf.loc[lrs.str.contains(motif, regex=False),
                           "facture_id"].dropna())

    return [
        ("MONTANT_NEGATIF", ids.isin(lines_with("MONTANT_NEGATIF"))
         | (df.montant_total < 0) | (df.montant_eligible < 0)),
        ("CODE_ACTE_INCONNU", ids.isin(lines_with("CODE_ACTE_INCONNU"))),
        ("LIGNE_INVALIDE", ids.isin(set(ldf.loc[lrs != "",
                                               "facture_id"].dropna()))),
        ("FACTURE_SANS_LIGNE", ~ids.isin(n_lines.index)),
        ("TOTAL_INCOHERENT", ids.isin(sum_m.index)
         & (pd.to_numeric(ids.map(sum_m), errors="coerce")
            != df.montant_total.astype("float64"))),
        ("NB_LIGNES_INCOHERENT", ids.isin(n_lines.index)
         & (pd.to_numeric(ids.map(n_lines), errors="coerce")
            != df.nb_lignes.astype("float64"))),
        ("DEVISE_INVALIDE", df.devise.notna() & (df.devise != "MGA")),
        ("DATE_FUTURE", df.date_soin > pd.Timestamp(ctx.today)),
        ("DATES_INCOHERENTES", (df.date_soin > df.date_facture)
         | (df.date_facture > df.date_reception)),
        ("ELIGIBLE_SUPERIEUR_TOTAL", df.montant_eligible > df.montant_total),
        ("VALEUR_INTERDITE:type_facture", en(df, "type_facture",
                                             CATEGORIES)),
        ("VALEUR_INTERDITE:canal_reception", en(
            df, "canal_reception", ["PAPIER_SCAN", "EMAIL",
                                    "PORTAIL_PRESTATAIRE"])),
        ("VALEUR_INTERDITE:mode_reglement", en(
            df, "mode_reglement", ["TIERS_PAYANT", "REMBOURSEMENT_ASSURE"])),
        ("VALEUR_INTERDITE:statut", en(df, "statut", ["PAYEE", "REJETEE",
                                                      "EN_COURS"])),
    ]


def warn_factures(df, ctx):
    return [("PRISE_EN_CHARGE_PLUS_RESTE_DIFFERENT_DU_TOTAL",
             df.montant_pris_en_charge + df.reste_a_charge
             != df.montant_total),
            ("REJETEE_SANS_MOTIF", (df.statut == "REJETEE")
             & df.motif_rejet.isna())]


def chk_labels_fraude(df, ctx):
    return [("VALEUR_INTERDITE:type_fraude", en(df, "type_fraude",
                                                FRAUD_TYPES)),
            ("VALEUR_INTERDITE:motif_invalidite",
             en(df, "motif_invalidite", INVALID_CODES))]


SPECS = {
    "referentiel_actes": spec(
        "code_acte",
        dict(code_acte="str", libelle="str", categorie="str",
             specialite="str", tarif_min="i64", tarif_reference="i64",
             tarif_max="i64", ordonnance_requise="bool",
             entente_prealable="bool", sexe_requis="str", age_min="i16",
             age_max="i16"),
        null=["specialite", "sexe_requis"], checks=chk_actes),
    "referentiel_medicaments": spec(
        "code_medicament",
        dict(code_medicament="str", libelle="str", prix_reference="i64",
             remboursable="bool", classe="str", chronique="bool"),
        checks=chk_meds),
    "garanties": spec(
        ["formule", "categorie"],
        dict(formule="str", categorie="str", taux_remboursement="i16",
             plafond_annuel_categorie="i64", franchise_par_facture="i64",
             delai_carence_jours="i16", plafond_annuel_global="i64",
             prime_annuelle_par_beneficiaire="i64",
             attestation_requise="bool", actes_exclus="arr",
             pieces_justificatives="str"),
        null=["actes_exclus"], checks=chk_garanties),
    "prestataires": spec(
        "prestataire_id",
        dict(prestataire_id="str", nom="str", type_prestataire="str",
             specialite="str", ville="str", quartier="str", adresse="str",
             telephone="str", numero_onm="str", nif="str", horaires="str",
             jours_ouverture="str", heure_ouverture="i16",
             heure_fermeture="i16", niveau_tarif="str", note_qualite="i16",
             conventionne="bool", date_conventionnement="date",
             date_fin_convention="date", statut="str"),
        null=["specialite", "numero_onm", "date_fin_convention"],
        regex=dict(prestataire_id=RX["PRE"], telephone=RX["TEL"],
                   nif=r"^\d{10}$", jours_ouverture=r"^[1-7]{1,7}$",
                   numero_onm=r"^ONM-\d{5}$"),
        checks=chk_prestataires),
    "grille_tarifaire": spec(
        ["prestataire_id", "code"],
        dict(prestataire_id="str", code="str", tarif_pratique="i64"),
        fks=[("prestataire_id", "prestataires", "PRESTATAIRE_INCONNU")],
        checks=chk_grille),
    "contrats": spec(
        "contrat_id",
        dict(contrat_id="str", numero_police="str", souscripteur_id="str",
             souscripteur_nom="str", secteur="str", formule="str",
             date_effet_police="date", date_effet="date", date_fin="date",
             statut="str", nb_beneficiaires="i16",
             prime_annuelle_totale="i64"),
        null=["date_fin"],
        regex=dict(contrat_id=RX["CTR"], souscripteur_id=RX["SOU"]),
        fks=[("formule", "garanties.formule", "FORMULE_INCONNUE")],
        checks=chk_contrats),
    "assures": spec(
        "assure_id",
        dict(assure_id="str", contrat_id="str", rang_beneficiaire="str",
             assure_principal_id="str", sexe="str", annee_naissance="i16",
             ville="str", date_adhesion="date", date_radiation="date"),
        null=["date_radiation"],
        regex=dict(assure_id=RX["ASS"], contrat_id=RX["CTR"],
                   assure_principal_id=RX["ASS"]),
        fks=[("contrat_id", "contrats", "CONTRAT_INCONNU")],
        checks=chk_assures),
    "identites_pii": spec(
        "assure_id",
        dict(assure_id="str", nom="str", prenoms="str", sexe="str",
             date_naissance="date", telephone="str", email="str",
             adresse="str", ville="str", numero_cin="str"),
        null=["telephone", "email", "numero_cin"],
        regex=dict(assure_id=RX["ASS"], numero_cin=r"^\d{12}$",
                   telephone=RX["TEL"], email=RX["MAIL"]),
        fks=[("assure_id", "assures", "ASSURE_INCONNU")],
        checks=chk_identites, sensitive=True),
    "ordonnances": spec(
        "ordonnance_id",
        dict(ordonnance_id="str", assure_id="str", prescripteur_id="str",
             date_prescription="date", validite_jours="i16",
             type_ordonnance="str", diagnostic="str",
             renseignement_clinique="str"),
        null=["diagnostic", "renseignement_clinique"],
        regex=dict(ordonnance_id=RX["ORD"], assure_id=RX["ASS"],
                   prescripteur_id=RX["PRE"]),
        fks=[("assure_id", "assures", "ASSURE_INCONNU"),
             ("prescripteur_id", "prestataires", "PRESCRIPTEUR_INCONNU")],
        checks=chk_ordonnances),
    "ordonnance_lignes": spec(
        ["ordonnance_id", "num_ligne"],
        dict(ordonnance_id="str", num_ligne="i16", code="str",
             libelle="str", quantite="i16", posologie="str"),
        null=["posologie"], regex=dict(ordonnance_id=RX["ORD"]),
        fks=[("ordonnance_id", "ordonnances", "ORDONNANCE_INCONNUE")],
        checks=chk_ord_lignes),
    "lignes_facture": spec(
        "ligne_id",
        dict(ligne_id="str", facture_id="str", num_ligne="i16", code="str",
             type_ligne="str", libelle="str", quantite="i16",
             prix_unitaire="i64", montant="i64"),
        regex=dict(ligne_id=RX["LIG"], facture_id=RX["FAC"]),
        checks=chk_lignes, warns=warn_lignes),
    "factures": spec(
        "facture_id",
        dict(facture_id="str", numero_facture="str", prestataire_id="str",
             assure_id="str", contrat_id="str", ordonnance_id="str",
             type_facture="str", date_soin="date", heure_soin="time",
             date_facture="date", date_reception="date",
             canal_reception="str", mode_reglement="str",
             attestation_pec_id="str", entente_prealable_id="str",
             devise="str", nb_lignes="i16", montant_total="i64",
             montant_eligible="i64", montant_pris_en_charge="i64",
             reste_a_charge="i64", statut="str", motif_rejet="str",
             date_traitement="date"),
        null=["ordonnance_id", "attestation_pec_id", "entente_prealable_id",
              "motif_rejet", "date_traitement"],
        regex=dict(facture_id=RX["FAC"], prestataire_id=RX["PRE"],
                   assure_id=RX["ASS"], contrat_id=RX["CTR"],
                   ordonnance_id=RX["ORD"]),
        fks=[("prestataire_id", "prestataires", "PRESTATAIRE_INCONNU"),
             ("assure_id", "assures", "ASSURE_INCONNU"),
             ("contrat_id", "contrats", "CONTRAT_INCONNU"),
             ("ordonnance_id", "ordonnances", "ORDONNANCE_INCONNUE")],
        checks=chk_factures, warns=warn_factures),
    "labels_fraude": spec(
        "facture_id",
        dict(facture_id="str", est_fraude="bool", type_fraude="str",
             detail_fraude="str", est_valide="bool",
             motif_invalidite="str"),
        null=["type_fraude", "detail_fraude", "motif_invalidite"],
        fks=[("facture_id", "factures", "FACTURE_INCONNUE")],
        checks=chk_labels_fraude, labels=True),
    "labels_prestataires": spec(
        "prestataire_id",
        dict(prestataire_id="str", est_suspect="bool"),
        fks=[("prestataire_id", "prestataires", "PRESTATAIRE_INCONNU")],
        labels=True),
}


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
class Ctx:
    def __init__(self, args):
        self.src = Path(args.src)
        self.labels_dir = Path(args.labels) if args.labels else None
        self.out = Path(args.out)
        self.rejets = Path(args.rejets)
        self.secure = Path(args.secure)
        self.today = dt.date.fromisoformat(args.today)
        self.keys: dict[str, set] = {}
        self.kept: dict[str, pd.DataFrame] = {}
        self.state: dict[str, dict] = {}
        self.manifest: dict = {"today": args.today, "inputs": {},
                               "tables": {}}
        self.written: dict[str, list[str]] = {}
        for d in (self.out, self.rejets, self.secure):
            d.mkdir(parents=True, exist_ok=True)


def source_path(ctx: Ctx, name: str, sp: dict) -> Path | None:
    base = ctx.labels_dir if sp["labels"] else ctx.src
    if base is None:
        return None
    return base / f"{sp['file'] or name}.csv"


def prepare(ctx: Ctx, name: str) -> bool:
    sp = SPECS[name]
    path = source_path(ctx, name, sp)
    if path is None or not path.exists():
        if sp["labels"]:
            ctx.manifest["tables"][name] = {"status": "source file absent"}
            print(f"  [skip] {name}: file not provided")
            return False
        raise SystemExit(f"ERROR: missing input file {path}")

    ctx.manifest["inputs"][path.name] = sha256_file(path)
    raw = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""],
                      encoding="utf-8-sig")
    expected = list(sp["cols"])
    missing = [c for c in expected if c not in raw.columns]
    if missing:
        raise SystemExit(f"ERROR: {path.name} lacks columns {missing}")
    extra = [c for c in raw.columns if c not in expected]
    if extra:
        print(f"  [warn] {path.name}: ignored extra columns {extra}")
    raw = raw[expected]
    n_in = len(raw)

    exact = raw.duplicated(keep="first")  # technical duplicates only
    n_exact = int(exact.sum())
    raw = raw[~exact]

    df = pd.DataFrame(index=raw.index)
    bad = {}
    masks: list[tuple[str, pd.Series]] = []
    for col, kind in sp["cols"].items():
        df[col], bad[col] = cast(raw[col], kind)
        label = "DATE_IMPOSSIBLE" if kind == "date" else "TYPE_INVALIDE"
        masks.append((f"{label}:{col}", bad[col]))
        if col not in sp["null"]:
            masks.append((f"CHAMP_OBLIGATOIRE_MANQUANT:{col}",
                          df[col].isna() & ~bad[col]))
    for col, pat in sp["regex"].items():
        ok = df[col].str.match(pat).fillna(True).astype(bool)
        masks.append((f"FORMAT_INVALIDE:{col}", ~ok))
    if len(sp["pk"]) == 1:
        masks.append(("CLE_DUPLIQUEE", df.duplicated(sp["pk"], keep="first")
                      & df[sp["pk"][0]].notna()))
    else:
        masks.append(("CLE_DUPLIQUEE", df.duplicated(sp["pk"], keep="first")
                      & df[sp["pk"]].notna().all(axis=1)))
    ctx.state[name] = dict(raw=raw, df=df, n_in=n_in, n_exact=n_exact)

    for col, parent, motif in sp["fks"]:
        masks.append((motif, df[col].notna()
                      & ~df[col].isin(ctx.keys[parent])))
    if sp["checks"]:
        masks += sp["checks"](df, ctx)

    ctx.state[name]["masks"] = masks
    ctx.state[name]["reasons"] = assemble(masks, df.index)
    return True


def assemble(masks, index) -> pd.Series:
    reasons = pd.Series("", index=index, dtype=object)
    for motif, m in masks:
        m = pd.Series(m, index=index).fillna(False).astype(bool)
        reasons = reasons.where(~m, reasons + motif + ";")
    return reasons


def commit(ctx: Ctx, name: str) -> None:
    sp, st = SPECS[name], ctx.state[name]
    df, raw = st["df"], st["raw"]
    reasons = assemble(st["masks"], df.index)
    kept_mask = reasons == ""
    kept = df[kept_mask]

    # counts per reject reason
    counts: dict[str, int] = {}
    for r in reasons[~kept_mask]:
        for motif in r.strip(";").split(";"):
            counts[motif] = counts.get(motif, 0) + 1

    warns = {}
    if sp["warns"]:
        for motif, m in sp["warns"](kept, ctx):
            n = int(pd.Series(m, index=kept.index).fillna(False).sum())
            if n:
                warns[motif] = n

    # rejects file (personal tables never leak values)
    rej_path = ctx.rejets / f"{name}.csv"
    if (~kept_mask).any():
        if sp["sensitive"]:
            rej = pd.DataFrame({"source_row": raw.index[~kept_mask] + 2,
                                sp["pk"][0]: raw.loc[~kept_mask, sp["pk"][0]]})
        else:
            rej = raw[~kept_mask].copy()
            rej.insert(0, "source_row", rej.index + 2)
        rej["motif"] = reasons[~kept_mask].str.rstrip(";")
        rej.to_csv(rej_path, index=False, encoding="utf-8")
    elif rej_path.exists():
        rej_path.unlink()

    # output
    cols = dict(sp["cols"])
    if name == "identites_pii":
        cols.pop("sexe")
        cols.pop("ville")
        target = ctx.secure / "identites_pii.parquet"
    else:
        target = ctx.out / f"{name}.parquet"
    pq.write_table(to_arrow(kept, cols), target, compression="zstd")
    ctx.written[name] = list(cols)

    # keys for downstream foreign keys
    if len(sp["pk"]) == 1:
        ctx.keys[name] = set(kept[sp["pk"][0]])
    ctx.kept[name] = kept
    if name == "garanties":
        ctx.keys["garanties.formule"] = set(kept["formule"])

    ctx.manifest["tables"][name] = {
        "rows_in": st["n_in"], "exact_duplicates_dropped": st["n_exact"],
        "rows_out": int(len(kept)), "rows_rejected": int((~kept_mask).sum()),
        "reject_reasons": dict(sorted(counts.items())),
        "warnings": warns,
        "output": target.name,
    }
    flag = "  <-- rejects" if (~kept_mask).any() else ""
    print(f"  {name:<26} in={st['n_in']:>7}  out={len(kept):>7}  "
          f"rejected={int((~kept_mask).sum()):>5}{flag}")
    for motif, n in warns.items():
        print(f"      [warn] {motif}: {n}")


def build_ref_codes(ctx: Ctx) -> None:
    a, m = ctx.kept["referentiel_actes"], ctx.kept["referentiel_medicaments"]
    ctx.keys["codes_actes"] = set(a.code_acte)
    ctx.keys["codes_meds"] = set(m.code_medicament)
    ctx.keys["ref_codes"] = ctx.keys["codes_actes"] | ctx.keys["codes_meds"]
    both = ctx.keys["codes_actes"] & ctx.keys["codes_meds"]
    if both:
        raise SystemExit(f"ERROR: codes in both referentials: {sorted(both)}")
    acts = pd.DataFrame({"code": a.code_acte, "type_ligne": "ACTE",
                         "libelle": a.libelle, "tarif_min": a.tarif_min,
                         "tarif_reference": a.tarif_reference,
                         "tarif_max": a.tarif_max})
    meds = pd.DataFrame({"code": m.code_medicament,
                         "type_ligne": "MEDICAMENT", "libelle": m.libelle,
                         "tarif_min": pd.array([pd.NA] * len(m),
                                               dtype="Int64"),
                         "tarif_reference": m.prix_reference,
                         "tarif_max": pd.array([pd.NA] * len(m),
                                               dtype="Int64")})
    cols = dict(code="str", type_ligne="str", libelle="str", tarif_min="i64",
                tarif_reference="i64", tarif_max="i64")
    ref = pd.concat([acts, meds], ignore_index=True)
    pq.write_table(to_arrow(ref, cols), ctx.out / "ref_codes.parquet",
                   compression="zstd")


def finalize_lines(ctx: Ctx) -> None:
    st = ctx.state["lignes_facture"]
    orphan = ~st["df"].facture_id.isin(ctx.keys["factures"])
    st["masks"].append(("FACTURE_REJETEE_OU_INCONNUE", orphan))
    commit(ctx, "lignes_facture")


def write_features(ctx: Ctx) -> None:
    f = ctx.kept["factures"]
    cols = {c: k for c, k in SPECS["factures"]["cols"].items()
            if c not in LEAK_COLS}
    pq.write_table(to_arrow(f, cols), ctx.out / "factures_features.parquet",
                   compression="zstd")
    ctx.written["factures_features"] = list(cols)


def check_no_pii_leak(ctx: Ctx) -> None:
    """Contract rule 7: personal columns only in identites_pii."""
    for name, cols in ctx.written.items():
        if name in ("identites_pii", "prestataires"):
            continue  # providers are fictional business entities
        leaked = PII_COLS & set(cols)
        if leaked:
            raise SystemExit(f"ERROR: personal columns {leaked} in {name}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--src", default="dataset")
    p.add_argument("--out", default="data/clean")
    p.add_argument("--rejets", default="data/rejets")
    p.add_argument("--secure", default="data/secure")
    p.add_argument("--labels", default=None,
                   help="folder with labels_fraude.csv / "
                        "labels_prestataires.csv (optional)")
    p.add_argument("--today", default=dt.date.today().isoformat(),
                   help="reference date for DATE_FUTURE (YYYY-MM-DD)")
    p.add_argument("--max-reject-ratio", type=float, default=0.05,
                   help="exit code 2 if a table rejects more than this share")
    args = p.parse_args(argv)
    ctx = Ctx(args)

    print(f"clean.py  src={ctx.src}  today={ctx.today}")
    for name in ("referentiel_actes", "referentiel_medicaments"):
        prepare(ctx, name)
        commit(ctx, name)
    build_ref_codes(ctx)
    for name in ("garanties", "prestataires", "grille_tarifaire", "contrats",
                 "assures", "identites_pii", "ordonnances",
                 "ordonnance_lignes"):
        prepare(ctx, name)
        commit(ctx, name)

    # invoices and lines depend on each other: lines first (no commit),
    # then invoices, then lines are finalised against kept invoices.
    prepare(ctx, "lignes_facture")
    prepare(ctx, "factures")
    commit(ctx, "factures")
    finalize_lines(ctx)
    write_features(ctx)

    for name in ("labels_fraude", "labels_prestataires"):
        if prepare(ctx, name):
            commit(ctx, name)

    check_no_pii_leak(ctx)
    (ctx.out / "_manifest.json").write_text(
        json.dumps(ctx.manifest, indent=2, sort_keys=True,
                   ensure_ascii=False), encoding="utf-8")

    worst = max((t["rows_rejected"] / t["rows_in"]
                 for t in ctx.manifest["tables"].values()
                 if t.get("rows_in")), default=0)
    print(f"\nDone. Output: {ctx.out}  Rejects: {ctx.rejets}  "
          f"Personal data: {ctx.secure} (never share, keep out of Git)")
    if worst > args.max_reject_ratio:
        print(f"ERROR: reject ratio {worst:.1%} above "
              f"{args.max_reject_ratio:.0%}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
