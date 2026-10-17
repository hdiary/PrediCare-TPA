"""Validation des factures entrantes : les 10 codes du contrat de données (section 9.1).

Réponse en cas d'échec : HTTP 422 avec la liste des codes. Deux codes supplémentaires,
propres à l'API, couvrent les cas que le contrat ne nomme pas :
  - CHAMP_INTERDIT : champ de fuite envoyé (statut, motif_rejet, montant_pris_en_charge, ...)
  - VALEUR_INVALIDE : format d'identifiant, valeur non entière, type ou catégorie inconnus...
Le numero_facture n'est JAMAIS dédoublonné (signal de fraude, voir 8.3 du contrat).
"""
import math
import re
from datetime import date, datetime, timedelta, timezone

from api import repositories as repo

MADAGASCAR_TZ = timezone(timedelta(hours=3))  # UTC+3, pas d'heure d'été

RE_ASSURE = re.compile(r"^ASS-[0-9A-F]{10}$")
RE_CONTRAT = re.compile(r"^CTR-\d{6}$")
RE_PRESTATAIRE = re.compile(r"^PRE-\d{5}$")
RE_FACTURE = re.compile(r"^FAC-\d{8}$")
RE_ORDONNANCE = re.compile(r"^ORD-\d{7}$")
RE_ATTESTATION = re.compile(r"^APC-\d{6}$")
RE_ENTENTE = re.compile(r"^EP-\d{5}$")
RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_HEURE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

CHAMPS_INTERDITS = ("statut", "motif_rejet", "montant_pris_en_charge", "reste_a_charge",
                    "date_traitement")
CHAMPS_OBLIGATOIRES = ("facture_id", "numero_facture", "prestataire_id", "assure_id",
                       "contrat_id", "type_facture", "date_soin", "heure_soin", "devise")
TYPES_LIGNE = {"ACTE", "MEDICAMENT"}
CANAUX = {"PAPIER_SCAN", "EMAIL", "PORTAIL_PRESTATAIRE"}
MODES = {"TIERS_PAYANT", "REMBOURSEMENT_ASSURE"}
MAX_LIGNES = 100
MAX_TEXTE = 64              # numero_facture et autres textes libres
MAX_CODE_LIGNE = 40
MAX_QUANTITE = 32767        # SMALLINT
MAX_MONTANT = 10**12


class InvoiceRejected(Exception):
    """Facture refusée : convertie en réponse 422 (ou 409) avec la liste des codes."""

    def __init__(self, erreurs: list[dict], status_code: int = 422):
        super().__init__("Facture rejetée")
        self.erreurs = erreurs
        self.status_code = status_code

    @property
    def codes(self) -> list[str]:
        return sorted({e["code"] for e in self.erreurs})


def today_mg() -> date:
    return datetime.now(MADAGASCAR_TZ).date()


def _err(errors: list[dict], code: str, champ: str, message: str) -> None:
    errors.append({"code": code, "champ": champ, "message": message})


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _int(value) -> int | None:
    """Entier (MGA) ou None. Refuse booléens, NaN, décimales non nulles."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if math.isfinite(value) and value == int(value) else None
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
        return int(value.strip())
    return None


def _parse_date(value) -> date | None:
    if not isinstance(value, str) or not RE_DATE.match(value.strip()):
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _text(raw: dict, key: str, errors: list[dict], pattern=None, invalid_code="VALEUR_INVALIDE"):
    """Texte nettoyé, ou None (absent => signalé par la boucle des champs obligatoires)."""
    value = raw.get(key)
    if _blank(value):
        return None
    if (
        not isinstance(value, str)
        or len(value.strip()) > MAX_TEXTE
        or (pattern and not pattern.match(value.strip()))
    ):
        _err(errors, invalid_code, key, "Format invalide")
        return None
    return value.strip()


def _montant(value, champ: str, errors: list[dict], *, strict_positive=False,
             maximum=MAX_MONTANT) -> int | None:
    if _blank(value):
        _err(errors, "CHAMP_OBLIGATOIRE_MANQUANT", champ, "Champ obligatoire")
        return None
    number = _int(value)
    if number is None:
        _err(errors, "VALEUR_INVALIDE", champ, "Entier attendu (MGA, sans décimales)")
        return None
    if number < 0 or (strict_positive and number == 0):
        _err(errors, "MONTANT_NEGATIF", champ, "Valeur négative ou nulle")
        return None
    if number > maximum:
        _err(errors, "VALEUR_INVALIDE", champ, "Valeur trop grande")
        return None
    return number


def _check_lignes(raw: dict, errors: list[dict], parsed: dict) -> None:
    lignes = raw.get("lignes")
    if lignes is None or lignes == []:
        _err(errors, "FACTURE_SANS_LIGNE", "lignes", "Aucune ligne de facture")
        return
    if not isinstance(lignes, list) or len(lignes) > MAX_LIGNES:
        _err(errors, "VALEUR_INVALIDE", "lignes", f"Liste de 1 à {MAX_LIGNES} lignes attendue")
        return

    out, somme, somme_ok = [], 0, True
    for i, ln in enumerate(lignes, start=1):
        champ = f"lignes[{i}]"
        if not isinstance(ln, dict):
            _err(errors, "VALEUR_INVALIDE", champ, "Objet attendu")
            somme_ok = False
            continue
        ok = True

        code = ln.get("code")
        if _blank(code):
            _err(errors, "CHAMP_OBLIGATOIRE_MANQUANT", f"{champ}.code", "Champ obligatoire")
            ok = False
        elif not isinstance(code, str) or len(code.strip()) > MAX_CODE_LIGNE:
            _err(errors, "VALEUR_INVALIDE", f"{champ}.code", "Texte de 40 caractères maximum")
            ok = False

        type_ligne = ln.get("type_ligne")
        if not _blank(type_ligne) and type_ligne not in TYPES_LIGNE:
            _err(errors, "VALEUR_INVALIDE", f"{champ}.type_ligne", "ACTE ou MEDICAMENT attendu")
            ok = False

        quantite = _montant(ln.get("quantite"), f"{champ}.quantite", errors,
                            strict_positive=True, maximum=MAX_QUANTITE)
        prix = _montant(ln.get("prix_unitaire"), f"{champ}.prix_unitaire", errors)
        if quantite is None or prix is None:
            ok = False

        if not _blank(ln.get("montant")):
            montant = _montant(ln.get("montant"), f"{champ}.montant", errors)
            if montant is not None and quantite is not None and prix is not None \
                    and montant != quantite * prix:
                _err(errors, "TOTAL_INCOHERENT", f"{champ}.montant",
                     "montant différent de quantite x prix_unitaire")
                ok = False

        if ok:
            out.append({"num_ligne": i, "code": code.strip(),
                        "type_ligne": type_ligne if not _blank(type_ligne) else None,
                        "quantite": quantite, "prix_unitaire": prix, "montant": quantite * prix})
            somme += quantite * prix
        else:
            somme_ok = False

    parsed["lignes"] = out
    if somme_ok:
        parsed["montant_total"] = somme

    if not _blank(raw.get("montant_total")):
        fourni = _montant(raw.get("montant_total"), "montant_total", errors)
        if fourni is not None and somme_ok and fourni != somme:
            _err(errors, "TOTAL_INCOHERENT", "montant_total",
                 "montant_total différent de la somme des lignes")


def validate_structure(raw: dict, today: date | None = None) -> tuple[list[dict], dict]:
    """Contrôles sans accès base. Retourne (erreurs, éléments valides déjà normalisés)."""
    errors: list[dict] = []
    parsed: dict = {}
    today = today or today_mg()

    for champ in CHAMPS_INTERDITS:
        if champ in raw:
            _err(errors, "CHAMP_INTERDIT", champ,
                 "Champ réservé au traitement interne : ne pas l'envoyer")
    for champ in CHAMPS_OBLIGATOIRES:
        if _blank(raw.get(champ)):
            _err(errors, "CHAMP_OBLIGATOIRE_MANQUANT", champ, "Champ obligatoire")

    parsed["facture_id"] = _text(raw, "facture_id", errors, RE_FACTURE)
    parsed["numero_facture"] = _text(raw, "numero_facture", errors)
    parsed["prestataire_id"] = _text(raw, "prestataire_id", errors, RE_PRESTATAIRE,
                                     "PRESTATAIRE_INCONNU")
    parsed["assure_id"] = _text(raw, "assure_id", errors, RE_ASSURE, "ASSURE_INCONNU")
    parsed["contrat_id"] = _text(raw, "contrat_id", errors, RE_CONTRAT)
    parsed["ordonnance_id"] = _text(raw, "ordonnance_id", errors, RE_ORDONNANCE)
    parsed["type_facture"] = _text(raw, "type_facture", errors)
    parsed["attestation_pec_id"] = _text(raw, "attestation_pec_id", errors, RE_ATTESTATION)
    parsed["entente_prealable_id"] = _text(raw, "entente_prealable_id", errors, RE_ENTENTE)

    for champ, allowed in (("canal_reception", CANAUX), ("mode_reglement", MODES)):
        value = raw.get(champ)
        if not _blank(value):
            if value not in allowed:
                _err(errors, "VALEUR_INVALIDE", champ, f"Valeurs admises : {sorted(allowed)}")
            else:
                parsed[champ] = value

    devise = raw.get("devise")
    if not _blank(devise):
        if not (isinstance(devise, str) and devise.strip() == "MGA"):
            _err(errors, "DEVISE_INVALIDE", "devise", "Seule la devise MGA est acceptée")
        else:
            parsed["devise"] = "MGA"

    date_soin = None
    if not _blank(raw.get("date_soin")):
        date_soin = _parse_date(raw["date_soin"])
        if date_soin is None:
            _err(errors, "DATE_IMPOSSIBLE", "date_soin", "Date non analysable (AAAA-MM-JJ)")
        elif date_soin > today:
            _err(errors, "DATE_FUTURE", "date_soin", "Date de soin dans le futur")
        else:
            parsed["date_soin"] = date_soin.isoformat()

    if not _blank(raw.get("heure_soin")):
        heure = raw["heure_soin"]
        if isinstance(heure, str) and RE_HEURE.match(heure.strip()):
            parsed["heure_soin"] = heure.strip()
        else:
            _err(errors, "DATE_IMPOSSIBLE", "heure_soin", "Heure invalide (HH:MM)")

    for champ in ("date_facture", "date_reception"):
        if not _blank(raw.get(champ)):
            value = _parse_date(raw[champ])
            if value is None:
                _err(errors, "DATE_IMPOSSIBLE", champ, "Date non analysable (AAAA-MM-JJ)")
            else:
                parsed[champ] = value.isoformat()
    df, dr = parsed.get("date_facture"), parsed.get("date_reception")
    if date_soin and df and df < date_soin.isoformat():
        _err(errors, "DATE_IMPOSSIBLE", "date_facture", "date_facture antérieure à date_soin")
    if df and dr and dr < df:
        _err(errors, "DATE_IMPOSSIBLE", "date_reception",
             "date_reception antérieure à date_facture")

    _check_lignes(raw, errors, parsed)
    return errors, {k: v for k, v in parsed.items() if v is not None}


def _db_checks(conn, parsed: dict, errors: list[dict]) -> None:
    if "assure_id" in parsed and not repo.assure_existe(conn, parsed["assure_id"]):
        _err(errors, "ASSURE_INCONNU", "assure_id", "Assuré inconnu")
    if "prestataire_id" in parsed and not repo.prestataire_existe(conn, parsed["prestataire_id"]):
        _err(errors, "PRESTATAIRE_INCONNU", "prestataire_id", "Prestataire inconnu")
    if "type_facture" in parsed and not repo.categorie_existe(conn, parsed["type_facture"]):
        _err(errors, "VALEUR_INVALIDE", "type_facture", "Catégorie de facture inconnue")

    lignes = parsed.get("lignes") or []
    if lignes:
        connus = repo.lookup_codes(conn, sorted({ln["code"] for ln in lignes}))
        for ln in lignes:
            ref = connus.get(ln["code"])
            if ref is None:
                _err(errors, "CODE_ACTE_INCONNU", f"lignes[{ln['num_ligne']}].code",
                     "Code absent des référentiels actes et médicaments")
            else:  # le référentiel fait foi pour le type et le libellé
                ln["type_ligne"] = ref["type_ligne"]
                ln["libelle"] = ref["libelle"]


def validate_invoice(raw: dict, conn) -> tuple[list[dict], dict | None]:
    """Retourne (erreurs, facture normalisée). La facture est None s'il y a des erreurs."""
    errors, parsed = validate_structure(raw)
    _db_checks(conn, parsed, errors)
    return errors, (None if errors else parsed)
