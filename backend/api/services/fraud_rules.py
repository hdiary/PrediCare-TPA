"""Deterministic pre scoring fraud checks.

The checks are deliberately side effect free; their codes are stored with the
prediction and are shown only to the gestionnaire response.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FraudFinding:
    code: str
    severity: str
    message: str
    details: dict


def evaluate_fraud_rules(clean: dict, context: dict) -> list[FraudFinding]:
    findings: list[FraudFinding] = []
    references = context.get("references", {})
    for line in clean.get("lignes", []):
        ref = references.get(line["code"], {})
        maximum = ref.get("tarif_max")
        if maximum is not None and line["prix_unitaire"] > maximum:
            findings.append(FraudFinding("SURFACTURATION", "HAUTE", "Tarif supérieur au référentiel", {"code": line["code"]}))
        if ref.get("type_ligne") and line.get("type_ligne") != ref["type_ligne"]:
            findings.append(FraudFinding("UPCODING", "MOYENNE", "Type de ligne incohérent", {"code": line["code"]}))
    provider = context.get("provider") or {}
    if provider.get("statut") == "RADIE":
        findings.append(FraudFinding("PRESTATAIRE_RADIE", "HAUTE", "Prestataire radié", {}))
    contract = context.get("contract") or {}
    if contract.get("statut") != "ACTIF":
        findings.append(FraudFinding("HORS_COUVERTURE", "HAUTE", "Contrat non actif", {}))
    return findings
