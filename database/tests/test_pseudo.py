"""
Tests for pseudo.py - run with:  pytest -v test_pseudo.py

The known-answer test freezes the algorithm: if someone changes pseudo.py in a
way that alters the output, it fails, because every pseudonym ever created
would silently change.
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

import database.pseudo as pseudo
from database.pseudo import PseudoError, pseudonymise, pseudonymise_many

HERE = Path(__file__).parent
SOURCE_ROOT = HERE.parent
KEY = "test-key-for-unit-tests-only-0123456789abcdef"
OTHER_KEY = "another-test-key-for-unit-tests-9876543210zyxw"
CONTRACT_RX = re.compile(r"^ASS-[0-9A-F]{10}$")  # contract section 3


# --- 1. Determinism (the core requirement) --------------------------------- #
def test_same_input_same_output():
    assert pseudonymise("ASSURE-TEST-001", key=KEY) == \
        pseudonymise("ASSURE-TEST-001", key=KEY)


def test_deterministic_across_processes_and_hash_seeds():
    """Same result in separate interpreters, whatever PYTHONHASHSEED is."""
    code = ("import pseudo;"
            f"print(pseudo.pseudonymise('ASSURE-TEST-001', key='{KEY}'))")
    results = set()
    for seed in ("0", "1", "12345", "random"):
        out = subprocess.run(
            [sys.executable, "-c", code], cwd=HERE, capture_output=True,
            text=True, check=True, env={"PYTHONHASHSEED": seed,
                                        "PATH": "/usr/bin:/bin",
                                        "PYTHONPATH": str(SOURCE_ROOT)})
        results.add(out.stdout.strip())
    assert len(results) == 1


def test_known_answer_vector_is_frozen():
    # Computed independently with:
    #   printf 'ASS|ASSURE-TEST-001' | openssl dgst -sha256 -hmac "$KEY"
    assert pseudonymise("ASSURE-TEST-001", "ASS", key=KEY) == "ASS-29A1BBF8EF"


# --- 2. Format ------------------------------------------------------------- #
def test_output_matches_contract_format():
    for i in range(500):
        assert CONTRACT_RX.match(pseudonymise(f"person-{i}", key=KEY))


def test_is_pseudonym_helper():
    assert pseudo.is_pseudonym("ASS-9CAA1484E0")  # a real dataset id
    assert not pseudo.is_pseudonym("ASS-9caa1484e0")  # lowercase
    assert not pseudo.is_pseudonym("ASS-9CAA1484E")  # too short
    assert not pseudo.is_pseudonym("PRE-00001")
    assert not pseudo.is_pseudonym("")


# --- 3. Keyed + separated -------------------------------------------------- #
def test_different_key_gives_different_pseudonym():
    assert pseudonymise("ASSURE-TEST-001", key=KEY) != \
        pseudonymise("ASSURE-TEST-001", key=OTHER_KEY)


def test_different_values_give_different_pseudonyms():
    values = [f"person-{i}" for i in range(5000)]
    pseudos = {pseudonymise(v, key=KEY) for v in values}
    assert len(pseudos) == len(values)


def test_output_does_not_contain_the_input():
    p = pseudonymise("RAKOTONORO Soa", key=KEY)
    assert "RAKOTONORO" not in p.upper()


# --- 4. Normalisation ------------------------------------------------------ #
@pytest.mark.parametrize("variant", ["assure-test-001", "  ASSURE-TEST-001 ",
                                     "ASSURE-TEST-001\n", "assure -test- 001"])
def test_normalisation_makes_variants_equal(variant):
    assert pseudonymise(variant, key=KEY) == \
        pseudonymise("ASSURE-TEST-001", key=KEY)


def test_unicode_equivalents_are_equal():
    # 'é' composed vs decomposed
    assert pseudonymise("André", key=KEY) == \
        pseudonymise("André", key=KEY)


# --- 5. Errors fail loudly ------------------------------------------------- #
@pytest.mark.parametrize("bad", ["", "   ", "\n\t"])
def test_empty_value_rejected(bad):
    with pytest.raises(PseudoError):
        pseudonymise(bad, key=KEY)


@pytest.mark.parametrize("bad", [None, 123, 4.5, b"bytes"])
def test_non_string_rejected(bad):
    with pytest.raises(PseudoError):
        pseudonymise(bad, key=KEY)


def test_unknown_prefix_rejected():
    with pytest.raises(PseudoError):
        pseudonymise("x", prefix="ZZZ", key=KEY)


def test_short_key_rejected():
    with pytest.raises(PseudoError):
        pseudonymise("x", key="too-short")


def test_missing_key_rejected(tmp_path):
    with pytest.raises(PseudoError, match="PSEUDO_KEY"):
        pseudo.load_key(environ={}, dotenv=tmp_path / "absent.env")


def test_key_read_from_environment():
    assert pseudo.load_key(environ={"PSEUDO_KEY": KEY}) == KEY.encode()


def test_key_read_from_dotenv_file(tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"# comment\nOTHER=1\nPSEUDO_KEY={KEY}\n")
    assert pseudo.load_key(environ={}, dotenv=env) == KEY.encode()


def test_environment_wins_over_dotenv(tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"PSEUDO_KEY={OTHER_KEY}\n")
    assert pseudo.load_key(environ={"PSEUDO_KEY": KEY},
                           dotenv=env) == KEY.encode()


# --- 6. Batch + collisions ------------------------------------------------- #
def test_batch_is_consistent_with_single_calls():
    values = ["a-1", "b-2", "c-3", "a-1"]
    out = pseudonymise_many(values, key=KEY)
    assert set(out) == {"a-1", "b-2", "c-3"}
    assert all(out[v] == pseudonymise(v, key=KEY) for v in out)


def test_batch_detects_collisions(monkeypatch):
    """Force every value onto one pseudonym: two people must not be merged."""
    monkeypatch.setattr(pseudo, "pseudonymise", lambda *a, **k: "ASS-0000000000")
    with pytest.raises(PseudoError, match="collision"):
        pseudonymise_many(["alice", "bob"], key=KEY)


def test_batch_same_person_twice_is_not_a_collision(monkeypatch):
    out = pseudonymise_many(["alice", " ALICE "], key=KEY)
    assert len(set(out.values())) == 1


# --- 7. CLI ---------------------------------------------------------------- #
def test_gen_key_is_long_and_random():
    keys = {pseudo.generate_key() for _ in range(20)}
    assert len(keys) == 20
    assert all(re.fullmatch(r"[0-9a-f]{64}", k) for k in keys)


def test_cli_without_key_fails_cleanly(tmp_path):
    r = subprocess.run([sys.executable, str(SOURCE_ROOT / "pseudo.py"), "ASS", "x"],
                       cwd=tmp_path, capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin"})
    assert r.returncode == 1 and "PSEUDO_KEY" in r.stderr
