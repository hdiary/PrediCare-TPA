from api.repositories_domain import list_invoice_lines, list_invoices


class FakeResult:
    def __init__(self, *, one=None, all_rows=None):
        self.one = one
        self.all_rows = all_rows or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.all_rows


class FakeConnection:
    def __init__(self, results):
        self.results = iter(results)
        self.queries = []

    def execute(self, query, params=()):
        self.queries.append((query, params))
        return next(self.results)


def test_list_invoices_applies_owner_and_status_filters():
    rows = [{"facture_id": "FAC-90000001"}]
    conn = FakeConnection(
        [
            FakeResult(one={"n": 1}),
            FakeResult(all_rows=rows),
        ]
    )

    result, total = list_invoices(
        conn,
        prestataire_id="PRE-00214",
        assure_id=None,
        statut="EN_COURS",
        limit=25,
        offset=5,
    )

    assert result == rows
    assert total == 1
    assert "WHERE prestataire_id = %s AND statut = %s" in conn.queries[0][0]
    assert conn.queries[0][1] == ("PRE-00214", "EN_COURS")
    assert "p.nom AS prestataire_nom" in conn.queries[1][0]
    assert "LEFT JOIN prestataires p" in conn.queries[1][0]
    assert "f.prestataire_id = %s AND f.statut = %s" in conn.queries[1][0]
    assert conn.queries[1][1] == ("PRE-00214", "EN_COURS", 25, 5)


def test_list_invoices_without_owner_or_status_lists_all_for_manager():
    conn = FakeConnection([FakeResult(one={"n": 0}), FakeResult()])

    rows, total = list_invoices(
        conn,
        prestataire_id=None,
        assure_id=None,
        statut=None,
        limit=50,
        offset=0,
    )

    assert rows == []
    assert total == 0
    assert " WHERE " not in conn.queries[0][0]
    assert conn.queries[0][1] == ()
    assert conn.queries[1][1] == (50, 0)


def test_list_invoice_lines_groups_lines_by_invoice():
    conn = FakeConnection(
        [
            FakeResult(
                all_rows=[
                    {
                        "facture_id": "FAC-90000001",
                        "num_ligne": 1,
                        "code": "CONS-GEN",
                        "libelle": "Consultation générale",
                        "quantite": 1,
                        "prix_unitaire": 50000,
                        "montant": 50000,
                    },
                    {
                        "facture_id": "FAC-90000002",
                        "num_ligne": 1,
                        "code": "MED-1",
                        "libelle": "Paracétamol",
                        "quantite": 1,
                        "prix_unitaire": 4000,
                        "montant": 4000,
                    },
                ]
            )
        ]
    )

    lines = list_invoice_lines(conn, ["FAC-90000001", "FAC-90000002"])

    assert lines["FAC-90000001"][0]["code"] == "CONS-GEN"
    assert lines["FAC-90000002"][0]["montant"] == 4000
    assert conn.queries[0][1] == (["FAC-90000001", "FAC-90000002"],)


def test_list_invoice_lines_skips_query_for_empty_invoice_list():
    conn = FakeConnection([])

    assert list_invoice_lines(conn, []) == {}
    assert conn.queries == []
