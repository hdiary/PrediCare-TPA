from api.repositories import list_utilisateurs


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows
        self.query = None

    def execute(self, query, params=()):
        self.query = (query, params)
        return FakeResult(self.rows)


def test_list_utilisateurs_shows_newest_accounts_first():
    rows = [{"utilisateur_id": 3}, {"utilisateur_id": 2}]
    conn = FakeConnection(rows)

    result = list_utilisateurs(
        conn,
        role=None,
        actif=None,
        q=None,
        limit=2,
        offset=0,
    )

    assert result == rows
    assert "ORDER BY u.utilisateur_id DESC LIMIT %s OFFSET %s" in conn.query[0]
    assert conn.query[1] == [2, 0]
