from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest

from api.services.ml_service import ModelRegistry, _sha256
from api.services.model_types import ModelBundle, ModelUnavailableError


def bundle(version):
    return ModelBundle("predicare-fraud", version, object(), object(), ["x"], datetime.now(UTC))


class RegistryConn:
    def __init__(self):
        self.rows = {
            "v1": {"version": "v1", "artifact_path": "/v1", "sha256": "a", "metrics": {}, "metadata": {}},
            "v2": {"version": "v2", "artifact_path": "/v2", "sha256": "b", "metrics": {}, "metadata": {}},
        }
        self.active = "v1"
        self.active_par = None
        self.audit = []
        self.updates = 0

    def execute(self, query, params=()):
        normalized = " ".join(query.split()).upper()
        if "WHERE VERSION = %S" in normalized:
            return Cursor(self.rows[params[0]])
        if "WHERE STATUS = 'ACTIF'" in normalized:
            return Cursor({"version": self.active})
        if normalized.startswith("UPDATE MODEL_VERSIONS"):
            self.updates += 1
            self.active = params[0]
            self.active_par = params[2]
            return Cursor(None)
        if normalized.startswith("INSERT INTO JOURNAL_AUDIT"):
            self.audit.append(params)
            return Cursor(None)
        raise AssertionError(query)

    @contextmanager
    def transaction(self):
        yield

    def commit(self):
        pass

    def rollback(self):
        pass


class Cursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


def test_corrupt_sha256_is_rejected_before_model_load(tmp_path: Path):
    artifact = tmp_path / "model.joblib"
    artifact.write_bytes(b"valid bytes")
    registry = ModelRegistry()
    with pytest.raises(ModelUnavailableError, match="SHA-256"):
        registry._load_record({
            "version": "v1",
            "artifact_path": str(artifact),
            "sha256": "0" * 64,
            "metrics": {},
            "metadata": {},
        })


def test_activation_then_rollback_updates_active_version_and_audit(monkeypatch):
    conn = RegistryConn()
    registry = ModelRegistry()
    monkeypatch.setattr(registry, "_load_record", lambda row: bundle(row["version"]))
    actor = {"user_id": 7}

    assert registry.activate_version(conn, "v2", actor).version == "v2"
    assert conn.active == "v2"
    assert registry.activate_version(conn, "v1", actor).version == "v1"
    assert conn.active == "v1"
    assert len(conn.audit) == 2
    assert conn.updates == 2
    assert conn.active_par == 7
    assert conn.audit[0][1] == 7
    assert conn.audit[0][3] == "v2"
    assert conn.audit[0][4].obj == {"previous_version": "v1", "action": "activate"}
    assert conn.audit[0][5].obj == {"active_version": "v2"}
    assert conn.audit[1][4].obj == {"previous_version": "v2", "action": "activate"}
    assert conn.audit[1][5].obj == {"active_version": "v1"}


def test_failed_candidate_keeps_old_bundle_and_does_not_update_database(monkeypatch):
    conn = RegistryConn()
    registry = ModelRegistry()
    old = bundle("v1")
    registry._bundle = old

    def fail(_):
        raise ModelUnavailableError("smoke test failed")

    monkeypatch.setattr(registry, "_load_record", fail)
    with pytest.raises(ModelUnavailableError):
        registry.activate_version(conn, "v2", {"user_id": 7})
    assert registry.get() is old
    assert conn.active == "v1"
    assert conn.updates == 0
    assert conn.audit == []


def test_sha_helper_is_deterministic(tmp_path: Path):
    path = tmp_path / "artifact"
    path.write_bytes(b"hello")
    assert _sha256(path) == _sha256(path)


def test_0012_role_order_and_optional_readonly_roles_are_guarded():
    root = Path(__file__).parents[1]
    migration = (root / "backend/ingestion/migrations/versions/0012_phase4_model_registry.py").read_text()
    roles_migration = (root / "backend/ingestion/migrations/versions/p1_0003_identites_et_roles.py").read_text()
    assert "down_revision = \"0011_auth_sessions\"" in migration
    assert "rolname = 'app_rw'" in migration
    assert "rolname = 'agent_ro'" in migration
    assert "rolname = 'ml_ro'" in migration
    assert "ARRAY['app_rw', 'identity_reader', 'agent_ro']" in roles_migration
