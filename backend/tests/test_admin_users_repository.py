from api import repositories
from api.repositories import list_utilisateurs


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


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


def test_invalider_jetons_reinitialisation_marque_les_jetons_actifs():
    conn = FakeConnection([])

    repositories.invalider_jetons_reinitialisation(conn, 42)

    assert "UPDATE reinitialisations_mdp SET utilise_le = now()" in conn.query[0]
    assert "utilise_le IS NULL" in conn.query[0]
    assert conn.query[1] == (42,)


def test_consommer_jeton_reinitialisation_retourne_le_compte():
    conn = FakeConnection([{"utilisateur_id": 42}])

    assert repositories.consommer_jeton_reinitialisation(conn, "hash") == 42
    assert "RETURNING utilisateur_id" in conn.query[0]
