#!/usr/bin/env python3
"""
pseudo.py - PrediCare TPA (P1): frozen, deterministic pseudonymisation.

Contract (v0.1, section 6.1)
----------------------------
- Algorithm : HMAC-SHA256(key=PSEUDO_KEY, msg="<PREFIX>|<normalised value>")
- Output    : "<PREFIX>-" + first 10 hex characters, UPPERCASE
              -> matches the contract regex ^ASS-[0-9A-F]{10}$
- Deterministic: same value + same key => same pseudonym, in any process,
  on any machine, after any restart.
- Keyed (HMAC, not a plain hash): identifiers have low entropy, so an
  unkeyed hash can be reversed by brute force.
- Domain separated: the prefix is part of the message, so the same raw value
  gives unrelated pseudonyms for different entity types.

IMPORTANT
---------
* The dataset's existing assure_id values are ALREADY pseudonyms (made with an
  unknown key). Do NOT recompute them: it would break the link with the RAG
  corpus, the example invoices and the labels. Use this module only for NEW
  insured persons and for tests.
* PSEUDO_KEY comes from the environment or a local .env file. It is never
  written in code and never committed. If it is lost or changed, every
  pseudonym created with it can no longer be reproduced.
* Do not change anything in this file's algorithm once the team has frozen it
  (the known-answer test in test_pseudo.py will fail if you do).

Usage
-----
    python pseudo.py --gen-key                 # print a fresh random key
    python pseudo.py ASS "value to pseudonymise"
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sys
import unicodedata
from pathlib import Path
from typing import Iterable, Mapping

# prefix -> number of hex characters kept
PREFIXES: dict[str, int] = {"ASS": 10}
MIN_KEY_LENGTH = 32
KEY_ENV_VAR = "PSEUDO_KEY"

_PSEUDO_RX = {p: re.compile(rf"^{p}-[0-9A-F]{{{n}}}$")
              for p, n in PREFIXES.items()}


class PseudoError(ValueError):
    """Raised for any misuse (missing key, bad prefix, empty value...)."""


# --------------------------------------------------------------------------- #
# Key handling
# --------------------------------------------------------------------------- #
def _read_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def load_key(environ: Mapping[str, str] | None = None,
             dotenv: Path | str = ".env") -> bytes:
    """Read PSEUDO_KEY (environment first, then .env). Never has a default."""
    env = os.environ if environ is None else environ
    key = env.get(KEY_ENV_VAR) or _read_dotenv(Path(dotenv)).get(KEY_ENV_VAR)
    if not key:
        raise PseudoError(
            f"{KEY_ENV_VAR} is not set. Generate one with "
            f"'python pseudo.py --gen-key' and put it in .env "
            f"(never in Git).")
    return _check_key(key.encode("utf-8"))


def _check_key(key: bytes) -> bytes:
    if len(key) < MIN_KEY_LENGTH:
        raise PseudoError(
            f"{KEY_ENV_VAR} is too short ({len(key)} bytes, "
            f"minimum {MIN_KEY_LENGTH}).")
    return key


def generate_key() -> str:
    """64 hex characters = 256 bits of randomness."""
    return secrets.token_hex(32)


# --------------------------------------------------------------------------- #
# Core
# --------------------------------------------------------------------------- #
def normalise(value: str) -> str:
    """Canonical form: NFKC, no whitespace at all, uppercase.

    'ab 12', ' AB12 ' and 'ab12' give the same pseudonym.
    """
    if not isinstance(value, str):
        raise PseudoError(f"value must be a string, got {type(value).__name__}")
    v = "".join(unicodedata.normalize("NFKC", value).split()).upper()
    if not v:
        raise PseudoError("value is empty after normalisation")
    return v


def pseudonymise(value: str, prefix: str = "ASS",
                 key: bytes | str | None = None) -> str:
    """Return the deterministic pseudonym of `value`."""
    if prefix not in PREFIXES:
        raise PseudoError(f"unknown prefix {prefix!r}; allowed: "
                          f"{sorted(PREFIXES)}")
    k = load_key() if key is None else _check_key(
        key.encode("utf-8") if isinstance(key, str) else key)
    msg = f"{prefix}|{normalise(value)}".encode("utf-8")
    digest = hmac.new(k, msg, hashlib.sha256).hexdigest().upper()
    return f"{prefix}-{digest[:PREFIXES[prefix]]}"


def is_pseudonym(value: str, prefix: str = "ASS") -> bool:
    return bool(_PSEUDO_RX[prefix].match(value or ""))


def pseudonymise_many(values: Iterable[str], prefix: str = "ASS",
                      key: bytes | str | None = None) -> dict[str, str]:
    """Pseudonymise a batch and refuse silent collisions.

    Returns {raw value: pseudonym}. With 10 hex characters (40 bits) a
    collision between two different values is very unlikely (about 1e-5 for
    4,500 people) but not impossible, so it is checked explicitly: two
    different normalised values mapping to one pseudonym raise an error
    instead of silently merging two people.
    """
    out: dict[str, str] = {}
    seen: dict[str, str] = {}  # pseudonym -> normalised value
    for raw in values:
        if raw in out:
            continue
        p = pseudonymise(raw, prefix, key)
        norm = normalise(raw)
        if p in seen and seen[p] != norm:
            raise PseudoError(f"collision: two different values give {p}")
        seen[p] = norm
        out[raw] = p
    return out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--gen-key"]:
        print(generate_key())
        return 0
    if len(argv) != 2:
        print(__doc__.split("Usage")[1].strip(), file=sys.stderr)
        return 1
    try:
        print(pseudonymise(argv[1], argv[0]))
    except PseudoError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
