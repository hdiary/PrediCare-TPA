"""
Integration tests for the database layer (migrations + load.py).

They need a THROWAWAY Postgres database and the raw dataset:

    export PREDICARE_TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/predicare_test
    export PREDICARE_DATASET=/path/to/CohorteAI_datagen/dataset
    export PGVECTOR_REQUIRED=0     # only if your Postgres has no pgvector
    pytest -v test_load.py

SAFETY: the schema `public` of the test database is DROPPED at the start. The
database name must contain 'test', otherwise every test is skipped.
Without both variables the whole module is skipped.
"""
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

HERE = Path(__file__).parent
ALEMBIC_DIR = HERE.parent.parent / "database"   # alembic.ini + migrations/
URL = os.environ.get("PREDICARE_TEST_DATABASE_URL")
DATASET = os.environ.get("PREDICARE_DATASET")

pytestmark = pytest.mark.skipif(
    not URL or not DATASET or "test" not in urlparse(URL).path,
    reason="set PREDICARE_TEST_DATABASE_URL (database name containing "
           "'test') and PREDICARE_DATASET")

LEAK = {"montant_pris_en_charge", "reste_a_charge", "statut", "motif_rejet",
        "date_traitement"}


def run(cmd, env_extra=None, check=True, cwd=None):
    env = {**os.environ, "DATABASE_URL": URL, **(env_extra or {})}
    r = subprocess.run(cmd, cwd=cwd or HERE, env=env, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise AssertionError(f"{cmd} failed:\n{r.stdout}\n{r.stderr}")
    return r


def load(clean, secure, *extra, check=True):
    return run([sys.executable, "load.py", "--clean-dir", str(clean),
                "--secure-dir", str(secure), "--include-operational-data",
                *extra], check=check)


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory):
    """Raw dataset -> clean.py -> encrypt_identities.py (real pipeline)."""
    base = tmp_path_factory.mktemp("pipeline")
    clean, rej, sec = base / "clean", base / "rejets", base / "secure"
    run([sys.executable, "clean.py", "--src", DATASET, "--out", str(clean),
         "--rejets", str(rej), "--secure", str(sec), "--today", "2026-10-14"])
    from cryptography.fernet import Fernet
    run([sys.executable, "encrypt_identities.py", "--in",
         str(sec / "identites_pii.parquet"), "--out",
         str(sec / "identites_chiffrees.parquet"), "--delete-source"],
        env_extra={"IDENTITY_KEY": Fernet.generate_key().decode()})
    return clean, sec


@pytest.fixture(scope="module")
def db(pipeline):
    """Fresh schema + migrations + first load. Returns a connection."""
    with psycopg.connect(URL, autocommit=True) as c:
        c.execute("DROP SCHEMA public CASCADE")
        c.execute("CREATE SCHEMA public")
    run(["alembic", "upgrade", "head"], cwd=ALEMBIC_DIR)
    clean, sec = pipeline
    load(clean, sec)
    conn = psycopg.connect(URL, autocommit=True)
    yield conn
    conn.close()


def count(conn, table):
    return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


# --- 1. first load --------------------------------------------------------- #
def test_every_table_has_the_rows_of_its_file(db, pipeline):
    clean, sec = pipeline
    expect = {"referentiel_actes": 58, "referentiel_medicaments": 28,
              "garanties": 27, "prestataires": 251, "grille_tarifaire": 3242,
              "contrats": 1500, "assures": 4459, "ordonnances": 47804,
              "ordonnance_lignes": 82175, "factures": 84593,
              "lignes_facture": 123270}
    for table, n in expect.items():
        assert count(db, table) == n, table
        assert pq.ParquetFile(clean / f"{table}.parquet").metadata.num_rows == n
    assert count(db, "identites_chiffrees") == 4459


def test_ingestion_log_has_one_row_per_file(db):
    rows = db.execute("SELECT fichier, lignes_lues, lignes_inserees, "
                      "lignes_mises_a_jour, lignes_rejetees FROM ingestion_log"
                      ).fetchall()
    assert len(rows) == 12
    assert all(r[1] == r[2] and r[3] == 0 and r[4] == 0 for r in rows)


# --- 2. idempotence -------------------------------------------------------- #
def test_second_run_changes_nothing(db, pipeline):
    before = {t: count(db, t) for t in ("factures", "lignes_facture",
                                        "identites_chiffrees")}
    log_before = count(db, "ingestion_log")
    r = load(*pipeline)
    assert " loaded " not in r.stdout          # every file skipped
    assert r.stdout.count(" skipped ") >= 12
    assert {t: count(db, t) for t in before} == before
    assert count(db, "ingestion_log") == log_before


def test_force_reload_inserts_and_updates_nothing(db, pipeline):
    r = load(*pipeline, "--force")
    for line in r.stdout.splitlines():
        if "loaded" in line:
            assert "inserted=      0 updated=    0" in line, line


def test_is_initialised(db, pipeline):
    r = run([sys.executable, "load.py", "--is-initialised",
             "--include-operational-data"], check=False)
    assert r.returncode == 0 and "initialised" in r.stdout


# --- 3. changed content is upserted --------------------------------------- #
def test_changed_file_updates_only_the_changed_row(db, pipeline, tmp_path):
    clean, sec = pipeline
    mod = tmp_path / "clean"
    mod.mkdir()
    t = pq.read_table(clean / "prestataires.parquet").to_pylist()
    old_note = t[0]["note_qualite"]
    t[0]["note_qualite"] = 1 if old_note != 1 else 2
    pq.write_table(pa.Table.from_pylist(
        t, schema=pq.read_schema(clean / "prestataires.parquet")),
        mod / "prestataires.parquet")
    # other required files: reuse the originals (already loaded -> skipped)
    for f in clean.glob("*.parquet"):
        if f.name != "prestataires.parquet":
            (mod / f.name).symlink_to(f)
    r = load(mod, sec)
    line = next(l for l in r.stdout.splitlines() if l.startswith("  prestataires"))
    assert "inserted=      0 updated=    1" in line, line
    assert count(db, "prestataires") == 251
    new = db.execute("SELECT note_qualite FROM prestataires WHERE "
                     "prestataire_id = %s", (t[0]["prestataire_id"],)
                     ).fetchone()[0]
    assert new == t[0]["note_qualite"]


# --- 4. all or nothing ----------------------------------------------------- #
def test_failing_file_is_rolled_back(db, pipeline, tmp_path):
    clean, sec = pipeline
    mod = tmp_path / "clean"
    mod.mkdir()
    schema = pq.read_schema(clean / "lignes_facture.parquet")
    rows = pq.read_table(clean / "lignes_facture.parquet").to_pylist()
    rows[0]["facture_id"] = "FAC-99999999"            # orphan -> FK violation
    rows[1]["libelle"] = "CHANGED"                     # a legit change too
    pq.write_table(pa.Table.from_pylist(rows, schema=schema),
                   mod / "lignes_facture.parquet")
    for f in clean.glob("*.parquet"):
        if f.name != "lignes_facture.parquet":
            (mod / f.name).symlink_to(f)
    n_before, log_before = count(db, "lignes_facture"), count(db, "ingestion_log")
    label_before = db.execute("SELECT libelle FROM lignes_facture WHERE "
                              "ligne_id = %s", (rows[1]["ligne_id"],)).fetchone()[0]
    r = load(mod, sec, check=False)
    assert r.returncode == 1 and "rolled back" in r.stderr
    assert count(db, "lignes_facture") == n_before
    assert count(db, "ingestion_log") == log_before
    assert db.execute("SELECT libelle FROM lignes_facture WHERE ligne_id = %s",
                      (rows[1]["ligne_id"],)).fetchone()[0] == label_before


# --- 5. personal data ------------------------------------------------------ #
def test_no_personal_column_outside_identity_table(db):
    bad = db.execute(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND column_name = ANY(%s) AND "
        "table_name NOT IN ('identites_chiffrees','prestataires','utilisateurs')",
        (["nom", "prenoms", "date_naissance", "telephone", "email", "adresse",
          "numero_cin"],)).fetchall()
    assert bad == []


def test_identity_table_holds_only_ciphertext(db):
    token = db.execute("SELECT donnees_chiffrees FROM identites_chiffrees "
                       "LIMIT 1").fetchone()[0]
    assert bytes(token).startswith(b"gAAAA")  # Fernet token prefix
    assert db.execute("SELECT count(*) FROM identites_chiffrees WHERE "
                      "key_version <> 1").fetchone()[0] == 0


def test_role_privileges(db):
    q = "SELECT has_table_privilege(%s, %s, %s)"
    can = lambda role, table, priv: db.execute(q, (role, table, priv)).fetchone()[0]
    assert can("app_rw", "factures", "INSERT")
    assert not can("app_rw", "identites_chiffrees", "SELECT")
    assert can("identity_reader", "identites_chiffrees", "SELECT")
    assert not can("identity_reader", "factures", "SELECT")
    assert not can("agent_ro", "factures", "SELECT")
    assert not can("public", "identites_chiffrees", "SELECT")


def test_app_rw_really_cannot_read_identities(db):
    with psycopg.connect(URL, autocommit=True) as c:
        c.execute("SET ROLE app_rw")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("SELECT * FROM identites_chiffrees").fetchall()
        c.execute("RESET ROLE")
        c.execute("SET ROLE identity_reader")
        assert c.execute("SELECT count(*) FROM identites_chiffrees"
                         ).fetchone()[0] == 4459


# --- 6. views -------------------------------------------------------------- #
def test_features_view_hides_leak_and_labels(db):
    cols = {r[0] for r in db.execute(
        "SELECT column_name FROM information_schema.columns WHERE "
        "table_name = 'v_factures_features'").fetchall()}
    assert cols and not (cols & LEAK)
    assert count(db, "v_factures_features") == count(db, "factures")


def test_ref_codes_view(db):
    assert count(db, "ref_codes") == 86
    types = dict(db.execute("SELECT type_ligne, count(*) FROM ref_codes "
                            "GROUP BY 1").fetchall())
    assert types == {"ACTE": 58, "MEDICAMENT": 28}


# --- 7. constraints -------------------------------------------------------- #
def test_database_rejects_invalid_invoice(db):
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("UPDATE factures SET devise = 'USD' WHERE facture_id = "
                   "'FAC-00000001'")
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        db.execute("UPDATE factures SET assure_id = 'ASS-0000000000' WHERE "
                   "facture_id = 'FAC-00000001'")


def test_suspicious_business_data_is_kept(db):
    """Repeated numero_facture / re-used ordonnance_id are fraud signals."""
    dup = db.execute("SELECT count(*) FROM (SELECT numero_facture FROM factures "
                     "GROUP BY 1 HAVING count(*) > 1) x").fetchone()[0]
    reuse = db.execute("SELECT count(*) FROM (SELECT ordonnance_id FROM factures "
                       "WHERE ordonnance_id IS NOT NULL GROUP BY 1 "
                       "HAVING count(*) > 1) x").fetchone()[0]
    assert dup > 0 and reuse > 0


def test_invoice_lines_sum_to_invoice_total(db):
    bad = db.execute("SELECT count(*) FROM factures f JOIN (SELECT facture_id, "
                     "sum(montant) s, count(*) n FROM lignes_facture GROUP BY 1) l "
                     "USING (facture_id) WHERE l.s <> f.montant_total OR "
                     "l.n <> f.nb_lignes").fetchone()[0]
    assert bad == 0


# --- 8. migrations are reversible (LAST: destroys the data) ---------------- #
def test_zzz_downgrade_to_base_then_upgrade(db):
    run(["alembic", "downgrade", "base"], cwd=ALEMBIC_DIR)
    left = db.execute("SELECT count(*) FROM information_schema.tables WHERE "
                      "table_schema='public' AND table_name <> "
                      "'alembic_version'").fetchone()[0]
    assert left == 0
    run(["alembic", "upgrade", "head"], cwd=ALEMBIC_DIR)
    assert count(db, "ingestion_log") == 0
    r = run([sys.executable, "load.py", "--is-initialised",
             "--include-operational-data"], check=False)
    assert r.returncode == 2
