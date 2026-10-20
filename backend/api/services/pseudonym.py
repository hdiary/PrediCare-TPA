"""Pseudonymes HMAC des comptes, conformes au contrat de P1."""
import hashlib
import hmac
import unicodedata

from api.config import get_settings

ROLE_PREFIXES = {
    "assure": "ASS",
    "gestionnaire": "GES",
    "professionnel_sante": "PDS",
    "administrateur": "ADM",
}


class PseudonymConfigurationError(ValueError):
    """La clé HMAC manque ou ne respecte pas la longueur minimale."""


def pseudonymise_account(value: str, role: str) -> str:
    prefix = ROLE_PREFIXES.get(role)
    if prefix is None:
        raise ValueError(f"Rôle inconnu pour la pseudonymisation : {role}")
    key = (get_settings().pseudo_hmac_key or "").strip().encode("utf-8")
    if len(key) < 32:
        raise PseudonymConfigurationError(
            "PSEUDO_HMAC_KEY doit contenir au moins 32 octets"
        )
    normalized = "".join(unicodedata.normalize("NFKC", value).split()).upper()
    if not normalized:
        raise ValueError("La valeur à pseudonymiser est vide")
    message = f"{prefix}|{normalized}".encode("utf-8")
    digest = hmac.new(key, message, hashlib.sha256).hexdigest().upper()
    return f"{prefix}-{digest[:10]}"
