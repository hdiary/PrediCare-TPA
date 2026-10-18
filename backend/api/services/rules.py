"""Règles métier de prescription (P3-16).

Complètent le score du modèle : chaque règle qui se déclenche produit une alerte de règle
(code, sévérité, message, détails) stockée dans `alertes_prescription` et montrée au gestionnaire.

IMPORTANT - à aligner avec P2 : le jeu de règles ci-dessous est un jeu par défaut, construit
uniquement avec des colonnes du contrat de données (factures, lignes_facture). Si P2 livre ses
propres règles, il suffit d'ajouter/remplacer des fonctions dans RULES : l'API, le stockage et
l'affichage n'ont pas à changer.

Une règle est une fonction `(conn, clean, ctx) -> list[Finding]`. Elle ne modifie jamais la base.
Une erreur dans une règle ne bloque jamais /predict (voir `evaluate_rules`).
"""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

SEVERITES = ("info", "moyenne", "haute")


@dataclass
class Finding:
    regle_code: str
    severite: str
    message: str
    details: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"regle_code": self.regle_code, "severite": self.severite,
                "message": self.message, "details": self.details}


def _quantite_max(conn, default: int = 10) -> int:
    try:
        row = conn.execute(
            "SELECT valeur FROM configuration WHERE cle = 'regle_quantite_max_medicament'"
        ).fetchone()
        return int(row["valeur"]) if row else default
    except (ValueError, TypeError, KeyError):
        return default


def rule_medicament_sans_ordonnance(conn, clean, ctx) -> list[Finding]:
    meds = [ln["code"] for ln in clean["lignes"] if ln["type_ligne"] == "MEDICAMENT"]
    if meds and not clean.get("ordonnance_id"):
        return [Finding("MEDICAMENT_SANS_ORDONNANCE", "haute",
                        "Médicament facturé sans ordonnance associée",
                        {"codes": sorted(set(meds))})]
    return []


def rule_ordonnance_reutilisee(conn, clean, ctx) -> list[Finding]:
    ordo = clean.get("ordonnance_id")
    if not ordo:
        return []
    rows = conn.execute(
        "SELECT facture_id FROM factures WHERE ordonnance_id = %s AND facture_id <> %s LIMIT 5",
        (ordo, clean["facture_id"]),
    ).fetchall()
    if rows:
        return [Finding("ORDONNANCE_REUTILISEE", "haute",
                        "Ordonnance déjà utilisée sur une autre facture",
                        {"ordonnance_id": ordo, "autres_factures": [r["facture_id"] for r in rows]})]
    return []


def rule_quantite_anormale(conn, clean, ctx) -> list[Finding]:
    seuil = _quantite_max(conn)
    hors = [{"code": ln["code"], "quantite": ln["quantite"]}
            for ln in clean["lignes"]
            if ln["type_ligne"] == "MEDICAMENT" and ln["quantite"] > seuil]
    if hors:
        return [Finding("QUANTITE_ANORMALE", "moyenne",
                        f"Quantité de médicament supérieure à {seuil} unités",
                        {"seuil": seuil, "lignes": hors})]
    return []


def rule_doublon_meme_jour(conn, clean, ctx) -> list[Finding]:
    codes = sorted({ln["code"] for ln in clean["lignes"]})
    rows = conn.execute(
        "SELECT DISTINCT f.facture_id, l.code FROM factures f "
        "JOIN lignes_facture l ON l.facture_id = f.facture_id "
        "WHERE f.assure_id = %s AND f.date_soin = %s AND f.facture_id <> %s "
        "AND l.code = ANY(%s) LIMIT 10",
        (clean["assure_id"], clean["date_soin"], clean["facture_id"], codes),
    ).fetchall()
    if rows:
        return [Finding("DOUBLON_MEME_JOUR", "moyenne",
                        "Même assuré et mêmes actes/médicaments facturés le même jour",
                        {"factures": sorted({r["facture_id"] for r in rows}),
                         "codes": sorted({r["code"] for r in rows})})]
    return []


RULES = [
    rule_medicament_sans_ordonnance,
    rule_ordonnance_reutilisee,
    rule_quantite_anormale,
    rule_doublon_meme_jour,
]


def evaluate_rules(conn, clean: dict, ctx: dict | None = None) -> list[Finding]:
    """Exécute toutes les règles. Une règle en erreur est ignorée (journalisée), jamais bloquante.

    Chaque règle tourne dans un savepoint : une erreur SQL n'abîme pas la transaction de /predict.
    """
    findings: list[Finding] = []
    for rule in RULES:
        try:
            with conn.transaction():
                findings.extend(rule(conn, clean, ctx or {}))
        except Exception as exc:  # noqa: BLE001
            logger.error("rule_failed rule=%s error=%s", rule.__name__, exc)
    return findings
