"""Explainable prescription checks, independent from the ML feature vector."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class PrescriptionFinding:
    code: str
    libelle: str
    details: dict = field(default_factory=dict)


def _date(value):
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def _quantity_threshold(conn, default: int = 10) -> int:
    try:
        row = conn.execute(
            "SELECT valeur FROM configuration WHERE cle = 'ordonnance_quantite_max'"
        ).fetchone()
        return int(row["valeur"]) if row else default
    except Exception:  # configuration is optional for this explainable check
        return default


def rule_ordonnance_falsifiee(conn, ordonnance: dict, lines: list[dict], context: dict) -> PrescriptionFinding | None:
    threshold = _quantity_threshold(conn)
    bad = [line for line in lines if int(line["quantite"]) > threshold]
    if not bad:
        return None
    return PrescriptionFinding(
        "ORDONNANCE_FALSIFIEE",
        "Quantité prescrite supérieure au seuil attendu",
        {"seuil": threshold, "lignes": [{"code": l["code"], "quantite": l["quantite"]} for l in bad]},
    )


def rule_prescripteur_incompatible(conn, ordonnance: dict, lines: list[dict], context: dict) -> PrescriptionFinding | None:
    prescriber = context.get("prescripteur") or {}
    specialty = prescriber.get("specialite")
    if not specialty:
        return None
    incompatible = []
    for line in lines:
        reference = context.get("actes", {}).get(line["code"]) or {}
        required = reference.get("specialite")
        if required and required != specialty:
            incompatible.append({"code": line["code"], "attendue": required, "prescripteur": specialty})
    if not incompatible:
        return None
    return PrescriptionFinding("PRESCRIPTEUR_INCOMPATIBLE", "Spécialité incompatible avec l'acte prescrit", {"lignes": incompatible})


def rule_prescripteur_radie(conn, ordonnance: dict, lines: list[dict], context: dict) -> PrescriptionFinding | None:
    prescriber = context.get("prescripteur") or {}
    end = prescriber.get("date_radiation") or prescriber.get("date_fin_convention")
    if not end or _date(ordonnance["date_prescription"]) <= _date(end):
        return None
    return PrescriptionFinding("PRESCRIPTEUR_RADIE", "Prescripteur radié à la date de prescription", {"date_fin": str(end)})


def rule_ordonnance_antidatee(conn, ordonnance: dict, lines: list[dict], context: dict) -> PrescriptionFinding | None:
    adhesion = (context.get("assure") or {}).get("date_adhesion")
    if not adhesion or _date(ordonnance["date_prescription"]) >= _date(adhesion):
        return None
    return PrescriptionFinding(
        "ORDONNANCE_ANTIDATEE",
        "Ordonnance antérieure à l'adhésion de l'assuré",
        {"date_prescription": str(ordonnance["date_prescription"]), "date_adhesion": str(adhesion)},
    )


RULES = (
    rule_ordonnance_falsifiee,
    rule_prescripteur_incompatible,
    rule_prescripteur_radie,
    rule_ordonnance_antidatee,
)


def load_prescription_context(conn, ordonnance_id: str) -> tuple[dict, list[dict], dict]:
    ordonnance = conn.execute("SELECT * FROM ordonnances WHERE ordonnance_id = %s", (ordonnance_id,)).fetchone()
    if not ordonnance:
        raise LookupError("Ordonnance introuvable")
    lines = conn.execute("SELECT * FROM ordonnance_lignes WHERE ordonnance_id = %s ORDER BY num_ligne", (ordonnance_id,)).fetchall()
    prescriber = conn.execute("SELECT * FROM prestataires WHERE prestataire_id = %s", (ordonnance["prescripteur_id"],)).fetchone()
    assure = conn.execute("SELECT * FROM assures WHERE assure_id = %s", (ordonnance["assure_id"],)).fetchone()
    codes = [line["code"] for line in lines]
    actes = {
        row["code_acte"]: row
        for row in conn.execute("SELECT * FROM referentiel_actes WHERE code_acte = ANY(%s)", (codes,)).fetchall()
    }
    return ordonnance, lines, {"prescripteur": prescriber, "assure": assure, "actes": actes}


def evaluate_prescription(conn, ordonnance_id: str) -> list[PrescriptionFinding]:
    ordonnance, lines, context = load_prescription_context(conn, ordonnance_id)
    return [finding for rule in RULES if (finding := rule(conn, ordonnance, lines, context))]
