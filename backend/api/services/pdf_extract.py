"""Lecture des PDF téléversés (factures et ordonnances) -> données structurées.

    from pdf_extract import extract_document
    res = extract_document(open("FAC-00005637.pdf", "rb").read(), ref=ref)
    res.doc_type   # "facture" | "ordonnance" | "inconnu"
    res.data       # champs lus (sans nom du patient)
    res.errors     # problèmes bloquants -> rejet propre de la facture
    res.warnings   # points à vérifier par un gestionnaire

Deux voies de lecture :
  1. PDF « texte » (généré par un logiciel) : lecture directe, rapide et fiable ;
  2. scan ou photo (aucun texte dans le PDF) : OCR Tesseract, moins fiable -> avertissement.

Respect du RGPD : le nom du patient n'est lu que pour contrôler que la facture et
l'ordonnance concernent la même personne ; il n'est jamais renvoyé ni stocké.
"""
from __future__ import annotations

import io
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

MIN_TEXT_CHARS = 80   # en dessous : on considère que le PDF est un scan
DATE = r"(\d{4}-\d{2}-\d{2})"


@dataclass
class Extraction:
    doc_type: str = "inconnu"
    method: str = "texte"            # "texte" ou "ocr"
    data: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


# --------------------------------------------------------------- lecture brute
def _clean(text: str) -> str:
    return text.replace("\u202f", " ").replace("\xa0", " ")


def read_text(pdf_bytes: bytes) -> tuple[str, str]:
    """Retourne (texte, méthode). Bascule sur l'OCR si le PDF n'a pas de couche texte."""
    import pdfplumber
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    if len(text.strip()) >= MIN_TEXT_CHARS:
        return _clean(text), "texte"
    return _clean(ocr_text(pdf_bytes)), "ocr"


def ocr_text(pdf_bytes: bytes) -> str:
    """OCR des pages (scan/photo). Langue : variable OCR_LANG (défaut fra+eng)."""
    import pytesseract
    from pdf2image import convert_from_bytes
    lang = os.getenv("OCR_LANG", "fra+eng")
    pages = convert_from_bytes(pdf_bytes, dpi=300)
    return "\n".join(pytesseract.image_to_string(p, lang=lang) for p in pages)


# ------------------------------------------------------------------- utilitaires
def _int(s: str) -> int:
    return int(re.sub(r"\D", "", s))


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().casefold()


def _valid_date(s: str | None) -> bool:
    try:
        date.fromisoformat(s or "")
        return True
    except ValueError:
        return False


def _find(pattern: str, text: str, flags: int = 0) -> str | None:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def _none(v: str | None) -> str | None:
    return None if v in (None, "—", "-", "") else v


# --------------------------------------------------------------------- facture
LINE_RE = re.compile(r"^([A-Z]{2,5}-[A-Z0-9]+)\s+(.+?)\s*Ar\s+(\d[\d ]*?)\s*Ar\s*$", re.M)


def _split_line(before_ar: str, montant: int) -> tuple[str, int, int]:
    """« désignation … 24 1 7 900 » -> (désignation, quantité, prix unitaire).

    Un nombre peut finir la désignation (« boîte de 24 ») et le prix peut contenir des
    espaces (« 7 900 ») : on essaie chaque découpage et on garde celui où
    quantité × prix unitaire = montant de la ligne."""
    toks = before_ar.split()
    run = 0
    while run < len(toks) and toks[-1 - run].isdigit():
        run += 1
    nums = toks[len(toks) - run:]
    first = None
    for k in range(1, len(nums)):                 # k = nombre de morceaux du prix
        pu_tokens = nums[-k:]
        if any(len(t) != 3 for t in pu_tokens[1:]):   # espace des milliers = groupes de 3 chiffres
            continue
        qte, pu = int(nums[-k - 1]), int("".join(pu_tokens))
        cand = (" ".join(toks[: len(toks) - k - 1]), qte, pu)
        first = first or cand
        if qte * pu == montant:
            return cand
    return first or (before_ar, 0, 0)


def parse_facture(text: str, ref: dict | None = None) -> Extraction:
    r = Extraction("facture")
    d = r.data
    d["numero_facture"] = _find(r"FACTURE\s+N°\s*(\S+)", text)
    d["date_soin"] = _find(rf"Date des soins\s+{DATE}", text)
    d["heure_soin"] = _find(r"Heure\s+(\d{2}:\d{2})", text)
    d["date_facture"] = _find(rf"Date de facture\s+{DATE}", text)
    d["type_facture"] = _find(r"Type\s+([A-Z_]+)", text)
    d["assure_id"] = _find(r"N°\s*assur[eé]\s+(ASS-[0-9A-Fa-f]+)", text)
    d["ordonnance_id"] = _none(_find(r"Ordonnance\s+(ORD-\d+|—)", text))
    d["attestation_pec_id"] = _none(_find(r"Attestation PEC\s+(APC-\d+|—)", text))
    d["entente_prealable_id"] = _none(_find(r"Entente pr[eé]alable\s+(\S+)", text))
    d["mode_reglement"] = _find(r"Mode\s+([A-Z_]+)", text)
    d["prestataire_nif"] = _find(r"NIF\s+(\d{10})", text)
    d["prestataire_nom"] = text.strip().splitlines()[0].strip() if text.strip() else None
    d["patient_present"] = bool(_find(r"Patient\s+(.+?)\s+N°\s*assur[eé]", text))
    total = _find(r"TOTAL\s+(\d[\d ]*?)\s*Ar", text)
    d["montant_total"] = _int(total) if total else None

    lines = []
    for code, avant, mont in LINE_RE.findall(text):
        lib, qte, pu = _split_line(avant.strip(), _int(mont))
        lines.append({"code": code, "libelle": lib.strip(), "quantite": qte,
                      "prix_unitaire": pu, "montant": _int(mont)})
    d["lignes"] = lines

    # ---- contrôles : rien d'incohérent n'entre dans le système
    for champ in ("numero_facture", "date_soin", "date_facture", "type_facture", "assure_id", "montant_total"):
        if not d.get(champ):
            r.errors.append(f"champ illisible ou absent : {champ}")
    if not lines:
        r.errors.append("aucune ligne de facture reconnue")
    for dt in ("date_soin", "date_facture"):
        if d.get(dt) and not _valid_date(d[dt]):
            r.errors.append(f"date invalide : {dt}")
    if _valid_date(d.get("date_soin")) and _valid_date(d.get("date_facture")) and d["date_facture"] < d["date_soin"]:
        r.errors.append("la date de facture précède la date des soins")
    for i, l in enumerate(lines, 1):
        if l["quantite"] * l["prix_unitaire"] != l["montant"]:
            r.errors.append(f"ligne {i} : quantité × prix unitaire ≠ montant")
    if lines and d.get("montant_total") is not None and sum(l["montant"] for l in lines) != d["montant_total"]:
        r.errors.append("la somme des lignes ne correspond pas au total")
    d["nb_lignes"] = len(lines)

    if ref:
        if d.get("prestataire_nif") and d["prestataire_nif"] not in ref["nif_to_prestataire"]:
            r.errors.append("prestataire inconnu (NIF absent du référentiel)")
        elif d.get("prestataire_nif"):
            d["prestataire_id"] = ref["nif_to_prestataire"][d["prestataire_nif"]]
        for l in lines:
            if l["code"] not in ref["codes"]:
                r.errors.append(f"code inconnu du référentiel : {l['code']}")
    return r


# ------------------------------------------------------------------ ordonnance
ORD_LINE_RE = re.compile(r"^\d+[\.\)]\s+(.+?)\s+[–—-]\s+Qt[eé]\s*[:;]?\s*(\d+)\s*$", re.M)


def parse_ordonnance(text: str, ref: dict | None = None) -> Extraction:
    r = Extraction("ordonnance")
    d = r.data
    d["ordonnance_id"] = _find(r"R[eé]f\.?\s*(ORD-\d+)", text)
    d["date_prescription"] = _find(rf",\s*le\s+{DATE}", text)
    d["validite_jours"] = int(_find(r"Validit[eé]\s*:\s*(\d+)\s*jours", text) or 0) or None
    d["prescripteur_onm"] = _find(r"(ONM-\d{5})", text)
    first = text.strip().splitlines()[0].strip() if text.strip() else ""
    d["prescripteur_etablissement"] = None if first.startswith(("Docteur", "Dr ")) else first
    d["renseignement_clinique"] = _find(r"Renseignement clinique\s*:\s*(.+)", text)
    spec = _find(r"^(.+?)\s+–\s+ONM-\d{5}", text, re.M)
    d["prescripteur_specialite"] = spec
    patient = re.search(r"Patient\s*:\s*(.+?)\s+–\s+(\d+)\s+ans", text)
    d["age_patient"] = int(patient.group(2)) if patient else None
    d["patient_present"] = bool(patient)

    ls = text.splitlines()
    lignes = []
    for i, line in enumerate(ls):
        m = ORD_LINE_RE.match(line.strip())
        if not m:
            continue
        nxt = next((x.strip() for x in ls[i + 1:] if x.strip()), "")
        poso = nxt if re.search(r"\d.*(jour|prise|cp|ml)", nxt, re.I) and not nxt.startswith(("À réaliser", "A réaliser", "A realiser", "Validit")) else None
        lib = m.group(1).strip()
        code = ref["label_to_code"].get(_norm(lib)) if ref else None
        if ref and code is None:
            r.warnings.append(f"désignation non reconnue dans le référentiel : {lib}")
        lignes.append({"libelle": lib, "code": code, "quantite": int(m.group(2)), "posologie": poso})
    d["lignes"] = lignes

    for champ in ("ordonnance_id", "date_prescription", "validite_jours"):
        if not d.get(champ):
            r.errors.append(f"champ illisible ou absent : {champ}")
    if d.get("date_prescription") and not _valid_date(d["date_prescription"]):
        r.errors.append("date de prescription invalide")
    if not lignes:
        r.errors.append("aucune ligne d'ordonnance reconnue")
    if not d.get("prescripteur_onm") and not d.get("prescripteur_etablissement"):
        r.errors.append("prescripteur : ni n° ONM ni établissement identifiable")   # médecin sans ONM
    if ref:
        if d.get("prescripteur_onm"):
            pid = ref["onm_to_prestataire"].get(d["prescripteur_onm"])
        else:
            pid = ref["name_to_prestataire"].get(_norm(d.get("prescripteur_etablissement") or ""))
        if pid:
            d["prescripteur_id"] = pid
        else:
            r.warnings.append("prescripteur absent du référentiel")
    return r


# ---------------------------------------------------------------------- entrée
def detect_type(text: str) -> str:
    if re.search(r"FACTURE\s+N°", text):
        return "facture"
    if re.search(r"ORDONNANCE", text) and re.search(r"Qt[eé]\s*[:;]", text):
        return "ordonnance"
    return "inconnu"


def extract_document(pdf_bytes: bytes, ref: dict | None = None) -> Extraction:
    """Point d'entrée : lit un PDF, devine son type, extrait et contrôle les champs."""
    if not pdf_bytes.startswith(b"%PDF"):
        return Extraction(errors=["le fichier n'est pas un PDF"])
    try:
        text, method = read_text(pdf_bytes)
    except Exception as e:  # PDF corrompu, protégé, OCR indisponible...
        return Extraction(errors=[f"lecture impossible : {type(e).__name__}"])
    kind = detect_type(text)
    if kind == "facture":
        res = parse_facture(text, ref)
    elif kind == "ordonnance":
        res = parse_ordonnance(text, ref)
    else:
        return Extraction(method=method, errors=["document non reconnu (ni facture ni ordonnance)"])
    res.method = method
    if method == "ocr":
        res.warnings.append("document lu par OCR : faire vérifier les champs par un gestionnaire")
    res.data.pop("patient_present", None)
    return res

def build_reference(tables: dict) -> dict:
    """Référentiels pour les contrôles (à construire une fois depuis la base).

    `tables` : dictionnaire de listes de dicts — clés 'referentiel_actes',
    'referentiel_medicaments', 'prestataires'.
    """
    acts = tables["referentiel_actes"]
    meds = tables["referentiel_medicaments"]
    both = [
        {"code": a["code"], "libelle": a["libelle"]} for a in acts
    ] + [
        {"code": m["code"], "libelle": m["libelle"]} for m in meds
    ]

    prestataires = tables["prestataires"]

    nif_to_prestataire = {
        str(p["nif"]): p["prestataire_id"]
        for p in prestataires
        if p.get("nif") not in (None, "", "nan")
    }

    onm_to_prestataire = {
        p["numero_onm"]: p["prestataire_id"]
        for p in prestataires
        if isinstance(p.get("numero_onm"), str) and p["numero_onm"]
    }

    # Noms uniques seulement (un nom en double est ambigu → ignoré)
    nom_counter: dict[str, int] = {}
    for p in prestataires:
        if p.get("nom"):
            key = _norm(p["nom"])
            nom_counter[key] = nom_counter.get(key, 0) + 1

    name_to_prestataire = {
        _norm(p["nom"]): p["prestataire_id"]
        for p in prestataires
        if p.get("nom") and nom_counter.get(_norm(p["nom"])) == 1
    }

    return {
        "codes": {row["code"] for row in both},
        "label_to_code": {_norm(row["libelle"]): row["code"] for row in both},
        "nif_to_prestataire": nif_to_prestataire,
        "onm_to_prestataire": onm_to_prestataire,
        "name_to_prestataire": name_to_prestataire,
    }
    """Référentiels pour les contrôles (à construire une fois depuis la base).

    `tables` : dictionnaire de listes de dicts — clés 'referentiel_actes',
    'referentiel_medicaments', 'prestataires'.
    """
    acts = tables["referentiel_actes"]
    meds = tables["referentiel_medicaments"]
    both = [
        {"code": a["code"], "libelle": a["libelle"]} for a in acts
    ] + [
        {"code": m["code"], "libelle": m["libelle"]} for m in meds
    ]

    prestataires = tables["prestataires"]

    nif_to_prestataire = {
        str(p["nif"]): p["prestataire_id"]
        for p in prestataires
        if p.get("nif") not in (None, "", "nan")
    }

    onm_to_prestataire = {
        p["numero_onm"]: p["prestataire_id"]
        for p in prestataires
        if isinstance(p.get("numero_onm"), str) and p["numero_onm"]
    }

    # Noms uniques seulement (un nom en double est ambigu → ignoré)
    nom_counter: dict[str, int] = {}
    for p in prestataires:
        if p.get("nom"):
            key = _norm(p["nom"])
            nom_counter[key] = nom_counter.get(key, 0) + 1

    name_to_prestataire = {
        _norm(p["nom"]): p["prestataire_id"]
        for p in prestataires
        if p.get("nom") and nom_counter.get(_norm(p["nom"])) == 1
    }

    return {
        "codes": {row["code"] for row in both},
        "label_to_code": {_norm(row["libelle"]): row["code"] for row in both},
        "nif_to_prestataire": nif_to_prestataire,
        "onm_to_prestataire": onm_to_prestataire,
        "name_to_prestataire": name_to_prestataire,
    }