import pytest

from api.bootstrap import _resolve_demo_provider_id


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.result = FakeResult(rows)
        self.query = ""
        self.params = None

    def execute(self, query, params=None):
        self.query = query
        self.params = params
        return self.result


def test_resolve_demo_provider_uses_the_configured_exact_name():
    conn = FakeConnection([{"prestataire_id": "PRE-00042"}])

    assert _resolve_demo_provider_id(conn, "Pharmacie Vatolampy") == "PRE-00042"
    assert "lower(btrim(nom)) = lower(btrim(%s))" in conn.query
    assert conn.params == ("Pharmacie Vatolampy",)


@pytest.mark.parametrize("rows", [[], [{"prestataire_id": "PRE-00001"}, {"prestataire_id": "PRE-00002"}]])
def test_resolve_demo_provider_rejects_missing_or_ambiguous_name(rows):
    with pytest.raises(RuntimeError, match="doit correspondre à une seule fiche active"):
        _resolve_demo_provider_id(FakeConnection(rows), "Pharmacie Vatolampy")