from api.repositories import list_audit


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.params = None

    def execute(self, query, params=()):
        self.query = query
        self.params = params
        return FakeResult(self.rows)


def test_list_audit_returns_audit_rows_with_role_and_event_filter():
    rows = [{"type_evenement": "decision", "role_acteur": "admin"}]
    conn = FakeConnection(rows)

    result = list_audit(conn, event_type="decision", limit=500)

    assert result == rows
    assert "FROM journal_audit a" in conn.query
    assert "a.type_evenement = %s" in conn.query
    assert "a.horodatage DESC, a.audit_id DESC" in conn.query
    assert conn.params == ("decision", 500, 0)


def test_list_audit_without_event_filter_uses_default_pagination():
    conn = FakeConnection([])

    result = list_audit(conn)

    assert result == []
    assert "FROM journal_audit a  ORDER BY" in conn.query
    assert "a.type_evenement = %s" not in conn.query
    assert conn.params == (100, 0)
