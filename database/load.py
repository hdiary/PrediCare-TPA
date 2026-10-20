#!/usr/bin/env python3
"""
load.py - PrediCare TPA (P1): idempotent, transactional load into Postgres.

Reads the Parquet files written by clean.py and encrypt_identities.py and
loads them in foreign-key order:

    <clean-dir>/*.parquet                        (referentials, business data)
    <secure-dir>/identites_chiffrees.parquet     (already encrypted)

Prerequisite: `alembic upgrade head` (tables must exist).

Guarantees
----------
* By default, loads reference and identity data only. Historical operational
  records (invoices, prescription records, and invoice labels) are excluded.
  Use --include-operational-data only for explicit archive/demo imports.
* Idempotent. Each file's SHA-256 is recorded in ingestion_log together with
  its name; a file whose (name, hash) is already there is skipped. Running
  the loader twice changes nothing.
* Re-loadable. If a file's content changed, its rows are upserted
  (INSERT ... ON CONFLICT DO UPDATE, only rows that really differ).
  Rows that disappeared from a file are NOT deleted.
* All or nothing per file: data + ingestion_log row are written in ONE
  transaction. A failure (e.g. foreign key violation) leaves the database
  exactly as before.
* Plaintext personal data never reaches the database: the loader refuses to
  finish if a personal column exists outside identites_chiffrees/prestataires.

Environment: DATABASE_URL=postgresql://user:password@host:5432/dbname

Usage
-----
    python load.py --clean-dir data/clean --secure-dir data/secure
    python load.py --include-operational-data  # explicit archive/demo import
    python load.py --is-initialised      # exit 0 if all files already loaded
    python load.py --wait 60 --wait-only # wait for the database, then exit
Exit codes: 0 ok, 1 error, 2 (--is-initialised) not initialised,
            3 row-count mismatch, 4 personal column found in database.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import psycopg
import pyarrow.parquet as pq

PII_COLS = {"nom", "prenoms", "date_naissance", "telephone", "email",
            "adresse", "numero_cin"}
# utilisateurs : adresses de connexion des comptes applicatifs (pas des assurés)
PII_ALLOWED_TABLES = {"identites_chiffrees", "prestataires", "utilisateurs"}
BATCH = 20_000


@dataclass(frozen=True)
class Source:
    table: str          # target table (and manifest key)
    folder: str         # 'clean' or 'secure'
    filename: str       # parquet file
    pk: tuple           # conflict target
    optional: bool = False
    manifest_key: str | None = None  # key in clean.py's manifest


# Foreign-key order: parents before children.
SOURCES = [
    Source("referentiel_actes", "clean", "referentiel_actes.parquet",
           ("code_acte",)),
    Source("referentiel_medicaments", "clean",
           "referentiel_medicaments.parquet", ("code_medicament",)),
    Source("garanties", "clean", "garanties.parquet",
           ("formule", "categorie")),
    Source("prestataires", "clean", "prestataires.parquet",
           ("prestataire_id",)),
    Source("grille_tarifaire", "clean", "grille_tarifaire.parquet",
           ("prestataire_id", "code")),
    Source("contrats", "clean", "contrats.parquet", ("contrat_id",)),
    Source("assures", "clean", "assures.parquet", ("assure_id",)),
    Source("identites_chiffrees", "secure", "identites_chiffrees.parquet",
           ("assure_id",), manifest_key="identites_pii"),
    Source("ordonnances", "clean", "ordonnances.parquet",
           ("ordonnance_id",)),
    Source("ordonnance_lignes", "clean", "ordonnance_lignes.parquet",
           ("ordonnance_id", "num_ligne")),
    Source("factures", "clean", "factures.parquet", ("facture_id",)),
    Source("lignes_facture", "clean", "lignes_facture.parquet",
           ("ligne_id",)),
    Source("labels_fraude", "clean", "labels_fraude.parquet",
           ("facture_id",), optional=True),
    Source("labels_prestataires", "clean", "labels_prestataires.parquet",
           ("prestataire_id",), optional=True),
]

OPERATIONAL_TABLES = frozenset({
    "ordonnances", "ordonnance_lignes", "factures", "lignes_facture",
    "labels_fraude",
})


def selected_sources(include_operational_data: bool = False) -> list[Source]:
    if include_operational_data:
        return SOURCES
    return [src for src in SOURCES if src.table not in OPERATIONAL_TABLES]


class LoadError(Exception):
    pass


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def connect(wait: int = 0) -> psycopg.Connection:
    url = os.environ.get("DATABASE_URL")
    # url = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@localhost:5432/{os.getenv('POSTGRES_DB')}"
    print("url : ", url)
    if not url:
        raise LoadError("DATABASE_URL is not set "
                        "(e.g. postgresql://user:pass@db:5432/predicare)")
    deadline = time.monotonic() + wait
    while True:
        try:
            # autocommit: every `with conn.transaction()` below is then a
            # REAL transaction (BEGIN/COMMIT), one per file.
            return psycopg.connect(url, connect_timeout=5, autocommit=True)
        except psycopg.OperationalError as exc:
            if time.monotonic() >= deadline:
                raise LoadError(f"cannot connect to the database: {exc}") \
                    from exc
            time.sleep(2)


def read_manifest(clean_dir: Path) -> dict:
    path = clean_dir / "_manifest.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")).get("tables", {})
    return {}


def source_path(src: Source, clean_dir: Path, secure_dir: Path) -> Path:
    return (clean_dir if src.folder == "clean" else secure_dir) / src.filename


def table_columns(conn, table: str) -> list[str]:
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s "
        "ORDER BY ordinal_position", (table,)).fetchall()
    return [r[0] for r in rows]


def already_loaded(conn, fichier: str, sha: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM ingestion_log WHERE fichier = %s AND sha256 = %s "
        "AND statut = 'OK'", (fichier, sha)).fetchone() is not None


# --------------------------------------------------------------------------- #
# Loading one table
# --------------------------------------------------------------------------- #
def load_table(conn, src: Source, path: Path, rejected: int,
               force: bool = False) -> dict:
    sha = sha256_file(path)
    if not force and already_loaded(conn, src.filename, sha):
        n = pq.ParquetFile(path).metadata.num_rows
        return {"table": src.table, "status": "skipped", "rows": n,
                "inserted": 0, "updated": 0}

    pf = pq.ParquetFile(path)
    cols = [f.name for f in pf.schema_arrow]
    db_cols = table_columns(conn, src.table)
    if not db_cols:
        raise LoadError(f"table {src.table} does not exist "
                        f"(run 'alembic upgrade head' first)")
    unknown = [c for c in cols if c not in db_cols]
    if unknown:
        raise LoadError(f"{src.filename}: columns {unknown} are not in "
                        f"table {src.table}")
    non_pk = [c for c in cols if c not in src.pk]
    col_list = ", ".join(cols)
    n_rows = pf.metadata.num_rows

    with conn.transaction():  # data + log row: all or nothing
        conn.execute(f"CREATE TEMP TABLE _stage (LIKE {src.table} "
                     f"INCLUDING DEFAULTS) ON COMMIT DROP")
        with conn.cursor() as cur:
            with cur.copy(f"COPY _stage ({col_list}) FROM STDIN") as copy:
                for batch in pf.iter_batches(batch_size=BATCH):
                    arrays = [batch.column(i).to_pylist()
                              for i in range(batch.num_columns)]
                    for row in zip(*arrays):
                        copy.write_row(row)

        # Only rows that really differ are updated (no useless dead tuples).
        sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in non_pk)
        old = ", ".join(f"{src.table}.{c}" for c in non_pk)
        new = ", ".join(f"EXCLUDED.{c}" for c in non_pk)
        sql = (f"INSERT INTO {src.table} ({col_list}) "
               f"SELECT {col_list} FROM _stage "
               f"ON CONFLICT ({', '.join(src.pk)}) DO UPDATE SET {sets} "
               f"WHERE ({old}) IS DISTINCT FROM ({new}) "
               f"RETURNING (xmax = 0)")
        flags = [r[0] for r in conn.execute(sql).fetchall()]
        inserted = sum(1 for f in flags if f)
        updated = len(flags) - inserted

        conn.execute(
            "INSERT INTO ingestion_log (fichier, sha256, lignes_lues, "
            "lignes_inserees, lignes_mises_a_jour, lignes_rejetees) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (fichier, sha256) DO NOTHING",
            (src.filename, sha, n_rows, inserted, updated, rejected))
    return {"table": src.table, "status": "loaded", "rows": n_rows,
            "inserted": inserted, "updated": updated}


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #
def check_counts(conn, results: list[dict]) -> list[str]:
    problems = []
    for r in results:
        n_db = conn.execute(f"SELECT count(*) FROM {r['table']}").fetchone()[0]
        if n_db != r["rows"]:
            problems.append(f"{r['table']}: file has {r['rows']} rows, "
                            f"database has {n_db}")
    return problems


def check_no_pii(conn) -> list[str]:
    rows = conn.execute(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND column_name = ANY(%s) "
        "AND table_name <> ALL(%s)",
        (sorted(PII_COLS), sorted(PII_ALLOWED_TABLES))).fetchall()
    # views and tables alike: a personal column must not exist elsewhere
    return [f"{t}.{c}" for t, c in rows]


def is_initialised(conn, clean_dir: Path, secure_dir: Path,
                   include_operational_data: bool = False) -> bool:
    try:
        done = {r[0] for r in conn.execute(
            "SELECT DISTINCT fichier FROM ingestion_log "
            "WHERE statut = 'OK'").fetchall()}
    except psycopg.errors.UndefinedTable:
        return False
    required = {s.filename for s in selected_sources(include_operational_data)
                if not s.optional}
    return required <= done

def create_database_if_not_exists(conn, db_name):
    """Vérifie si la base de données existe, sinon la crée."""
    conn.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
    if not conn.fetchone():
        print(f"Database '{db_name}' does not exist. Creating it...")
        conn.execute(f"CREATE DATABASE {db_name}")
        print(f"Database '{db_name}' created successfully.")


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--clean-dir", default="data/clean")
    p.add_argument("--secure-dir", default="data/secure")
    p.add_argument("--force", action="store_true",
                   help="reload even if the file hash is already logged")
    p.add_argument("--include-operational-data", action="store_true",
                   help="also load historical invoices, prescriptions, and invoice labels")
    p.add_argument("--skip-identities", action="store_true",
                   help="do not load identites_chiffrees (e.g. no key yet)")
    p.add_argument("--is-initialised", action="store_true",
                   help="exit 0 if every required file is already loaded")
    p.add_argument("--wait", type=int, default=0, metavar="SECONDS",
                   help="retry the connection for up to N seconds")
    p.add_argument("--wait-only", action="store_true",
                   help="only wait for the database (with --wait), then exit")
    args = p.parse_args(argv)
    clean_dir, secure_dir = Path(args.clean_dir), Path(args.secure_dir)

    try:
        conn = connect(wait=args.wait)
    except LoadError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    with conn:
        if args.wait_only:
            print("database reachable")
            return 0
        if args.is_initialised:
            ok = is_initialised(
                conn, clean_dir, secure_dir, args.include_operational_data)
            print("initialised" if ok else "not initialised")
            return 0 if ok else 2

        manifest = read_manifest(clean_dir)
        results = []
        print(f"load.py  clean={clean_dir}  secure={secure_dir}")
        try:
            for src in selected_sources(args.include_operational_data):
                if src.table == "identites_chiffrees" and args.skip_identities:
                    print(f"  {src.table:<26} skipped (--skip-identities)")
                    continue
                path = source_path(src, clean_dir, secure_dir)
                if not path.exists():
                    if src.optional:
                        print(f"  {src.table:<26} skipped (file absent)")
                        continue
                    raise LoadError(f"missing file {path}")
                rejected = manifest.get(src.manifest_key or src.table, {}
                                        ).get("rows_rejected", 0)
                r = load_table(conn, src, path, rejected, force=args.force)
                results.append(r)
                print(f"  {r['table']:<26} {r['status']:<8} rows={r['rows']:>7} "
                      f"inserted={r['inserted']:>7} updated={r['updated']:>5}")
        except (LoadError, psycopg.Error) as exc:
            print(f"ERROR: {exc}\nThe failing file was rolled back; files "
                  f"loaded before it stay loaded.", file=sys.stderr)
            return 1

        problems = check_counts(conn, results)
        if problems:
            print("ERROR: row-count mismatch:\n  " + "\n  ".join(problems),
                  file=sys.stderr)
            return 3
        leaked = check_no_pii(conn)
        if leaked:
            print(f"ERROR: personal columns found in database: {leaked}",
                  file=sys.stderr)
            return 4
        print("Verified: row counts match the files; no personal column "
              "outside identites_chiffrees.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
