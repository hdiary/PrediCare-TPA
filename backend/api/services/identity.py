"""Déchiffrement des identités (Fernet) : uniquement pour afficher une alerte à un gestionnaire.

Contrat de données, section 6.4 : seul P3 déchiffre ; le modèle, le RAG et l'agent n'y accèdent pas.
Contenu chiffré : JSON {nom, prenoms, date_naissance, telephone, email, adresse, numero_cin}.
On ne renvoie que nom, prénoms, téléphone et email (minimisation).
"""
import base64
import json
import re
from datetime import date

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


def encrypt_account_identity(fields: dict) -> bytes:
    """Chiffre les champs personnels avant leur insertion en base."""
    data = dict(fields)
    if isinstance(data.get("date_naissance"), date):
        data["date_naissance"] = data["date_naissance"].isoformat()
    try:
        return _fernet().encrypt(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise IdentityUnavailableError("identité invalide") from exc


def decrypt_account_identity(blob) -> dict:
    """Déchiffre une identité de compte pour les opérations d'administration internes."""
    try:
        data = json.loads(_fernet().decrypt(bytes(blob)))
    except InvalidToken as exc:
        raise IdentityUnavailableError("la clé ne correspond pas aux données du compte") from exc
    if not isinstance(data, dict):
        raise IdentityUnavailableError("identité de compte invalide")
    return data
