"""
Tests for encrypt_identities.py - run with:  pytest -v test_encrypt_identities.py
"""
import datetime as dt
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from cryptography.fernet import Fernet

import database.encrypt_identities as ei
from database.encrypt_identities import (IdentityError, decrypt_identity,
                                encrypt_identity, load_keyring)

HERE = Path(__file__).parent
SOURCE_ROOT = HERE.parent
K1 = Fernet.generate_key().decode()
K2 = Fernet.generate_key().decode()

PERSON = {"nom": "RAKOTONORO", "prenoms": "Soa Hanitra",
          "date_naissance": dt.date(1976, 1, 7), "telephone": "034 00 343 93",
          "email": "soa.rakotonoro36@exemple-fictif.mg",
          "adresse": "Lot III B 47 Mahamasina", "numero_cin": "121144065218"}


@pytest.fixture
def ring():
    return load_keyring(environ={"IDENTITY_KEY": K1}, dotenv="/nonexistent")


def make_source(path, people):
    cols = ["assure_id", *ei.FIELDS]
    data = {c: [p.get(c) for p in people] for c in cols}
    schema = pa.schema([("assure_id", pa.string()), ("nom", pa.string()),
                        ("prenoms", pa.string()),
                        ("date_naissance", pa.date32()),
                        ("telephone", pa.string()), ("email", pa.string()),
                        ("adresse", pa.string()), ("numero_cin", pa.string())])
    pq.write_table(pa.table(data, schema=schema), path)


# --- round trip ------------------------------------------------------------ #
def test_roundtrip_returns_all_seven_fields(ring):
    token, version = encrypt_identity("ASS-0000000001", PERSON, ring)
    got = decrypt_identity(token, "ASS-0000000001", version, ring)
    assert set(got) == set(ei.FIELDS)
    assert got["nom"] == "RAKOTONORO"
    assert got["date_naissance"] == "1976-01-07"
    assert got["numero_cin"] == "121144065218"


def test_null_fields_are_preserved(ring):
    person = {**PERSON, "telephone": None, "email": None, "numero_cin": None}
    token, v = encrypt_identity("ASS-0000000001", person, ring)
    got = decrypt_identity(token, "ASS-0000000001", v, ring)
    assert got["telephone"] is None and got["email"] is None
    assert got["numero_cin"] is None and got["nom"] == "RAKOTONORO"


def test_unicode_survives(ring):
    person = {**PERSON, "prenoms": "André Élise", "adresse": "Antsirabe – Lot 5"}
    token, v = encrypt_identity("ASS-0000000001", person, ring)
    got = decrypt_identity(token, "ASS-0000000001", v, ring)
    assert got["prenoms"] == "André Élise"
    assert got["adresse"] == "Antsirabe – Lot 5"


# --- confidentiality ------------------------------------------------------- #
def test_ciphertext_contains_no_plaintext(ring):
    token, _ = encrypt_identity("ASS-0000000001", PERSON, ring)
    for secret in (b"RAKOTONORO", b"Soa Hanitra", b"121144065218",
                   b"exemple-fictif", b"Mahamasina", b"1976"):
        assert secret not in token


def test_encryption_is_not_deterministic_but_both_decrypt(ring):
    t1, v = encrypt_identity("ASS-0000000001", PERSON, ring)
    t2, _ = encrypt_identity("ASS-0000000001", PERSON, ring)
    assert t1 != t2
    assert decrypt_identity(t1, "ASS-0000000001", v, ring) == \
        decrypt_identity(t2, "ASS-0000000001", v, ring)


# --- integrity ------------------------------------------------------------- #
def test_wrong_key_fails(ring):
    token, v = encrypt_identity("ASS-0000000001", PERSON, ring)
    other = load_keyring(environ={"IDENTITY_KEY": K2}, dotenv="/nonexistent")
    with pytest.raises(IdentityError, match="wrong key"):
        decrypt_identity(token, "ASS-0000000001", v, other)


def test_tampered_token_fails(ring):
    token, v = encrypt_identity("ASS-0000000001", PERSON, ring)
    tampered = bytearray(token)
    tampered[len(tampered) // 2] ^= 0x01
    with pytest.raises(IdentityError):
        decrypt_identity(bytes(tampered), "ASS-0000000001", v, ring)


def test_ciphertext_copied_to_another_person_is_rejected(ring):
    token, v = encrypt_identity("ASS-0000000001", PERSON, ring)
    with pytest.raises(IdentityError, match="does not belong"):
        decrypt_identity(token, "ASS-0000000002", v, ring)


def test_unknown_key_version_fails(ring):
    token, _ = encrypt_identity("ASS-0000000001", PERSON, ring)
    with pytest.raises(IdentityError, match="key_version=9"):
        decrypt_identity(token, "ASS-0000000001", 9, ring)


# --- keys ------------------------------------------------------------------ #
def test_missing_key_is_explicit():
    with pytest.raises(IdentityError, match="IDENTITY_KEY"):
        load_keyring(environ={}, dotenv="/nonexistent")


@pytest.mark.parametrize("bad", ["short", "not base64 !!", "a" * 44])
def test_invalid_key_rejected(bad):
    with pytest.raises(IdentityError, match="valid Fernet key"):
        load_keyring(environ={"IDENTITY_KEY": bad}, dotenv="/nonexistent")


def test_key_from_dotenv_and_environment_priority(tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"IDENTITY_KEY={K1}\n")
    assert load_keyring(environ={}, dotenv=env).current == 1
    ring = load_keyring(environ={"IDENTITY_KEY": K2}, dotenv=env)
    token, v = encrypt_identity("ASS-0000000001", PERSON, ring)
    only_k2 = load_keyring(environ={"IDENTITY_KEY": K2}, dotenv="/nonexistent")
    assert decrypt_identity(token, "ASS-0000000001", v, only_k2)["nom"]


def test_key_rotation_old_rows_still_readable():
    old = load_keyring(environ={"IDENTITY_KEY": K1}, dotenv="/nonexistent")
    token, v_old = encrypt_identity("ASS-0000000001", PERSON, old)
    assert v_old == 1
    new = load_keyring(environ={"IDENTITY_KEY": K2, "IDENTITY_KEY_VERSION": "2",
                                "IDENTITY_KEY_V1": K1}, dotenv="/nonexistent")
    assert new.current == 2
    assert decrypt_identity(token, "ASS-0000000001", 1, new)["nom"] == "RAKOTONORO"
    _, v_new = encrypt_identity("ASS-0000000001", PERSON, new)
    assert v_new == 2


def test_bad_version_rejected():
    for bad in ("0", "abc", "40000"):
        with pytest.raises(IdentityError):
            load_keyring(environ={"IDENTITY_KEY": K1,
                                  "IDENTITY_KEY_VERSION": bad},
                         dotenv="/nonexistent")


# --- files ----------------------------------------------------------------- #
def test_encrypt_file_end_to_end(tmp_path, ring):
    src, dst = tmp_path / "pii.parquet", tmp_path / "enc.parquet"
    people = [{"assure_id": f"ASS-{i:010X}", **PERSON, "nom": f"NOM{i}"}
              for i in range(50)]
    make_source(src, people)
    now = dt.datetime(2026, 10, 14, 1, 0, tzinfo=dt.timezone.utc)
    assert ei.encrypt_file(src, dst, ring, now=now) == 50
    assert ei.verify_file(src, dst, ring) == 50

    out = pq.read_table(dst)
    assert out.schema.equals(ei.OUT_SCHEMA)
    assert out.column_names == ["assure_id", "donnees_chiffrees",
                                "key_version", "created_at"]
    raw_bytes = dst.read_bytes()
    assert b"NOM7" not in raw_bytes and b"exemple-fictif" not in raw_bytes
    assert not (tmp_path / "enc.parquet.tmp").exists()


def test_verify_detects_a_swapped_row(tmp_path, ring):
    src, dst = tmp_path / "pii.parquet", tmp_path / "enc.parquet"
    make_source(src, [{"assure_id": "ASS-0000000001", **PERSON},
                      {"assure_id": "ASS-0000000002", **PERSON, "nom": "AUTRE"}])
    ei.encrypt_file(src, dst, ring)
    rows = pq.read_table(dst).to_pylist()
    rows[0]["donnees_chiffrees"], rows[1]["donnees_chiffrees"] = \
        rows[1]["donnees_chiffrees"], rows[0]["donnees_chiffrees"]
    pq.write_table(pa.Table.from_pylist(rows, schema=ei.OUT_SCHEMA), dst)
    with pytest.raises(IdentityError):
        ei.verify_file(src, dst, ring)


def test_duplicate_ids_rejected(tmp_path, ring):
    src = tmp_path / "pii.parquet"
    make_source(src, [{"assure_id": "ASS-0000000001", **PERSON}] * 2)
    with pytest.raises(IdentityError, match="unique"):
        ei.encrypt_file(src, tmp_path / "o.parquet", ring)


def test_missing_columns_rejected(tmp_path, ring):
    src = tmp_path / "pii.parquet"
    pq.write_table(pa.table({"assure_id": ["ASS-0000000001"], "nom": ["X"]}), src)
    with pytest.raises(IdentityError, match="lacks columns"):
        ei.encrypt_file(src, tmp_path / "o.parquet", ring)


# --- CLI ------------------------------------------------------------------- #
def run_cli(args, env, cwd):
    return subprocess.run([sys.executable, str(SOURCE_ROOT / "encrypt_identities.py"),
                           *args], cwd=cwd, capture_output=True, text=True,
                          env={"PATH": "/usr/bin:/bin", **env})


def test_cli_gen_key_gives_a_usable_key(tmp_path):
    r = run_cli(["--gen-key"], {}, tmp_path)
    assert r.returncode == 0
    Fernet(r.stdout.strip().encode())  # raises if invalid


def test_cli_encrypts_verifies_and_deletes_source(tmp_path):
    src, dst = tmp_path / "pii.parquet", tmp_path / "enc.parquet"
    make_source(src, [{"assure_id": "ASS-0000000001", **PERSON}])
    r = run_cli(["--in", str(src), "--out", str(dst), "--delete-source"],
                {"IDENTITY_KEY": K1}, tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Verified 1/1" in r.stdout
    assert dst.exists() and not src.exists()


def test_cli_keeps_source_without_flag(tmp_path):
    src, dst = tmp_path / "pii.parquet", tmp_path / "enc.parquet"
    make_source(src, [{"assure_id": "ASS-0000000001", **PERSON}])
    r = run_cli(["--in", str(src), "--out", str(dst)], {"IDENTITY_KEY": K1},
                tmp_path)
    assert r.returncode == 0 and src.exists() and "WARNING" in r.stdout


def test_cli_without_key_fails_cleanly_and_keeps_source(tmp_path):
    src, dst = tmp_path / "pii.parquet", tmp_path / "enc.parquet"
    make_source(src, [{"assure_id": "ASS-0000000001", **PERSON}])
    r = run_cli(["--in", str(src), "--out", str(dst), "--delete-source"], {},
                tmp_path)
    assert r.returncode == 1 and "IDENTITY_KEY" in r.stderr
    assert src.exists() and not dst.exists()
