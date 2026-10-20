from datetime import date
from types import SimpleNamespace

import pytest

from api.services import identity, pseudonym


PSEUDO_KEY = "test-key-for-unit-tests-only-0123456789abcdef"
FERNET_KEY = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="


def test_account_pseudonym_matches_the_p1_hmac_contract(monkeypatch):
    monkeypatch.setattr(
        pseudonym, "get_settings",
        lambda: SimpleNamespace(pseudo_hmac_key=PSEUDO_KEY),
    )
    assert pseudonym.pseudonymise_account("ASSURE-TEST-001", "assure") == \
        "ASS-29A1BBF8EF"
    assert pseudonym.pseudonymise_account("1234 5678 9012", "gestionnaire").startswith("GES-")
    assert pseudonym.pseudonymise_account("123456789012", "professionnel_sante").startswith("PDS-")
    assert pseudonym.pseudonymise_account("123456789012", "administrateur").startswith("ADM-")


def test_account_pseudonym_requires_a_configured_key(monkeypatch):
    monkeypatch.setattr(
        pseudonym, "get_settings",
        lambda: SimpleNamespace(pseudo_hmac_key=None),
    )
    with pytest.raises(pseudonym.PseudonymConfigurationError):
        pseudonym.pseudonymise_account("123456789012", "assure")


def test_account_identity_is_encrypted_and_roundtrips(monkeypatch):
    monkeypatch.setattr(
        identity, "get_settings",
        lambda: SimpleNamespace(identity_encryption_key=FERNET_KEY),
    )
    fields = {
        "nom": "Rakoto",
        "prenoms": "Soa",
        "sexe": "F",
        "date_naissance": date(1985, 3, 4),
        "telephone": "0340000000",
        "email": "soa@example.test",
        "adresse": "Lot 10",
        "ville": "Antananarivo",
        "numero_cin": "123456789012",
    }
    encrypted = identity.encrypt_account_identity(fields)
    assert b"123456789012" not in encrypted
    decrypted = identity.decrypt_account_identity(encrypted)
    assert decrypted["date_naissance"] == "1985-03-04"
    assert decrypted["numero_cin"] == fields["numero_cin"]
