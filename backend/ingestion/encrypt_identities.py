#!/usr/bin/env python3
"""
encrypt_identities.py - PrediCare TPA (P1): encrypt personal data (Fernet).

Reads  <secure>/identites_pii.parquet        (written by clean.py)
Writes <secure>/identites_chiffrees.parquet  (ready for load.py -> Postgres)

Output columns = contract table `identites_chiffrees` (section 6.4):
    assure_id         TEXT        clear, join key (already a pseudonym)
    donnees_chiffrees BYTEA       Fernet token of the JSON identity
    key_version       SMALLINT    which key encrypted it (rotation-ready)
    created_at        TIMESTAMPTZ UTC

Design
------
* Encryption happens HERE, in the application, before Postgres: the key never
  appears in SQL, so it never reaches Postgres logs and the database alone
  cannot decrypt its own identities.
* Fernet = AES-128-CBC + HMAC-SHA256 (authenticated: tampering is detected).
  A fresh random IV is used each time, so encrypting twice gives different
  bytes (expected). load.py must therefore upsert on assure_id.
* The assure_id is stored INSIDE the encrypted payload and checked on
  decryption, so a ciphertext copied onto another row is rejected.
* Only the service that shows an alert to an authorised manager (P3) holds
  IDENTITY_KEY in production. P2 (model), P4 (RAG/agent) never get it.

Keys (environment first, then .env; never in code or Git)
---------------------------------------------------------
    IDENTITY_KEY          current key (Fernet key, see --gen-key)
    IDENTITY_KEY_VERSION  its version number, default 1
    IDENTITY_KEY_V<n>     optional older keys, to keep decrypting old rows

Usage
-----
    python encrypt_identities.py --gen-key
    python encrypt_identities.py --in data/secure/identites_pii.parquet \
        --out data/secure/identites_chiffrees.parquet [--delete-source]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pyarrow as pa
import pyarrow.parquet as pq
from cryptography.fernet import Fernet, InvalidToken

FIELDS = ("nom", "prenoms", "date_naissance", "telephone", "email",
          "adresse", "numero_cin")
KEY_ENV = "IDENTITY_KEY"
VERSION_ENV = "IDENTITY_KEY_VERSION"
_OLD_KEY_RX = re.compile(r"^IDENTITY_KEY_V(\d+)$")


class IdentityError(Exception):
    """Any encryption / decryption / key problem."""


# --------------------------------------------------------------------------- #
# Keys
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Keyring:
    current: int
    keys: dict  # version -> Fernet


def _read_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _fernet(raw: str, name: str) -> Fernet:
    try:
        return Fernet(raw.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise IdentityError(
            f"{name} is not a valid Fernet key (44-char urlsafe base64). "
            f"Generate one with 'python encrypt_identities.py --gen-key'."
        ) from exc


def generate_key() -> str:
    return Fernet.generate_key().decode("ascii")


def load_keyring(environ: Mapping[str, str] | None = None,
                 dotenv: Path | str = ".env") -> Keyring:
    env = {**_read_dotenv(Path(dotenv)),
           **(os.environ if environ is None else environ)}
    if not env.get(KEY_ENV):
        raise IdentityError(
            f"{KEY_ENV} is not set. Generate one with "
            f"'python encrypt_identities.py --gen-key' and put it in .env "
            f"(never in Git).")
    try:
        current = int(env.get(VERSION_ENV, "1"))
    except ValueError as exc:
        raise IdentityError(f"{VERSION_ENV} must be an integer") from exc
    if not 1 <= current <= 32767:
        raise IdentityError(f"{VERSION_ENV} must be between 1 and 32767")
    keys = {current: _fernet(env[KEY_ENV], KEY_ENV)}
    for name, value in env.items():
        m = _OLD_KEY_RX.match(name)
        if m and value:
            version = int(m.group(1))
            if version in keys:
                raise IdentityError(f"two keys for version {version}")
            keys[version] = _fernet(value, name)
    return Keyring(current=current, keys=keys)


# --------------------------------------------------------------------------- #
# One identity
# --------------------------------------------------------------------------- #
def _plain(value):
    if value is None:
        return None
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return str(value)


def encrypt_identity(assure_id: str, fields: Mapping, keyring: Keyring
                     ) -> tuple[bytes, int]:
    """Return (Fernet token, key_version)."""
    payload = {"assure_id": assure_id,
               **{f: _plain(fields.get(f)) for f in FIELDS}}
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":")).encode("utf-8")
    return keyring.keys[keyring.current].encrypt(raw), keyring.current


def decrypt_identity(token: bytes, assure_id: str, key_version: int,
                     keyring: Keyring) -> dict:
    """Decrypt and return the 7 personal fields (without assure_id)."""
    fernet = keyring.keys.get(key_version)
    if fernet is None:
        raise IdentityError(f"no key available for key_version={key_version}")
    try:
        raw = fernet.decrypt(bytes(token))
    except InvalidToken as exc:
        raise IdentityError("cannot decrypt: wrong key or corrupted data"
                            ) from exc
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("assure_id") != assure_id:
        raise IdentityError("ciphertext does not belong to this assure_id")
    return {f: payload.get(f) for f in FIELDS}


# --------------------------------------------------------------------------- #
# Files
# --------------------------------------------------------------------------- #
OUT_SCHEMA = pa.schema([
    ("assure_id", pa.string()),
    ("donnees_chiffrees", pa.binary()),
    ("key_version", pa.int16()),
    ("created_at", pa.timestamp("us", tz="UTC")),
])


def encrypt_file(src: Path, dst: Path, keyring: Keyring,
                 now: dt.datetime | None = None) -> int:
    table = pq.read_table(src)
    missing = [c for c in ("assure_id", *FIELDS) if c not in table.column_names]
    if missing:
        raise IdentityError(f"{src.name} lacks columns {missing}")
    rows = table.to_pylist()
    ids = [r["assure_id"] for r in rows]
    if len(set(ids)) != len(ids) or any(not i for i in ids):
        raise IdentityError("assure_id must be present and unique")
    now = now or dt.datetime.now(dt.timezone.utc)

    tokens, versions = [], []
    for r in rows:
        token, version = encrypt_identity(r["assure_id"], r, keyring)
        tokens.append(token)
        versions.append(version)
    out = pa.Table.from_arrays(
        [pa.array(ids, pa.string()), pa.array(tokens, pa.binary()),
         pa.array(versions, pa.int16()),
         pa.array([now] * len(ids), pa.timestamp("us", tz="UTC"))],
        schema=OUT_SCHEMA)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    pq.write_table(out, tmp, compression="zstd")
    os.replace(tmp, dst)  # atomic: never a half-written output
    return len(ids)


def verify_file(src: Path, dst: Path, keyring: Keyring) -> int:
    """Decrypt every row of dst and compare with the plaintext source."""
    plain = {r["assure_id"]: r for r in pq.read_table(src).to_pylist()}
    enc = pq.read_table(dst).to_pylist()
    if len(enc) != len(plain):
        raise IdentityError(f"row count differs: {len(plain)} vs {len(enc)}")
    for e in enc:
        got = decrypt_identity(e["donnees_chiffrees"], e["assure_id"],
                               e["key_version"], keyring)
        want = {f: _plain(plain[e["assure_id"]].get(f)) for f in FIELDS}
        if got != want:
            raise IdentityError(f"round-trip mismatch for {e['assure_id']}")
    return len(enc)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--gen-key", action="store_true",
                   help="print a new Fernet key and exit")
    p.add_argument("--in", dest="src", default="data/secure/identites_pii.parquet")
    p.add_argument("--out", dest="dst",
                   default="data/secure/identites_chiffrees.parquet")
    p.add_argument("--delete-source", action="store_true",
                   help="delete the plaintext file after a successful "
                        "round-trip verification")
    args = p.parse_args(argv)

    if args.gen_key:
        print(generate_key())
        return 0
    try:
        keyring = load_keyring()
        src, dst = Path(args.src), Path(args.dst)
        n = encrypt_file(src, dst, keyring)
        v = verify_file(src, dst, keyring)
    except (IdentityError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Encrypted {n} identities (key_version={keyring.current}) -> {dst}")
    print(f"Verified {v}/{n} by full decryption and comparison.")
    if args.delete_source:
        src.unlink()
        print(f"Deleted plaintext source {src}")
    else:
        print(f"WARNING: plaintext file {src} still exists. Delete it "
              f"(--delete-source) and keep its folder out of Git.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
