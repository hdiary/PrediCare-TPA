"""Déchiffrement des identités (Fernet) : uniquement pour afficher une alerte à un gestionnaire.

Contrat de données, section 6.4 : seul P3 déchiffre ; le modèle, le RAG et l'agent n'y accèdent pas.
Contenu chiffré : JSON {nom, prenoms, date_naissance, telephone, email, adresse, numero_cin}.
On ne renvoie que nom, prénoms, téléphone et email (minimisation).
"""
import base64
import json
import re

from cryptography.fernet import Fernet, InvalidToken

from api.config import get_settings


class IdentityUnavailableError(Exception):
    """Clé absente/invalide ou données non déchiffrables."""


def _fernet() -> Fernet:
    key = (get_settings().identity_encryption_key or "").strip()
    if not key:
        raise IdentityUnavailableError("IDENTITY_ENCRYPTION_KEY absente")
    if re.fullmatch(r"[0-9a-fA-F]{64}", key):  # clé hex (openssl rand -hex 32) -> format Fernet
        key = base64.urlsafe_b64encode(bytes.fromhex(key)).decode()
    try:
        return Fernet(key.encode())
    except ValueError as exc:
        raise IdentityUnavailableError("IDENTITY_ENCRYPTION_KEY invalide") from exc


def decrypt_identity(blob) -> dict:
    try:
        data = json.loads(_fernet().decrypt(bytes(blob)))
    except InvalidToken as exc:
        raise IdentityUnavailableError("la clé ne correspond pas aux données") from exc
    return {k: data.get(k) for k in ("nom", "prenoms", "telephone", "email")}
