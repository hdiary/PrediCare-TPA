from contextlib import nullcontext

from api.routers.bi import _compute_kpis


class LiveBiConnection:
    def __init__(self):
        self.queries = []

    def transaction(self):
        return nullcontext()

    def execute(self, query, params=()):
        query = " ".join(query.split()).upper()
        self.queries.append(query)
        if "AS FACTURES_TRAITEES" in query:
            return _Result({
                "factures_enregistrees": 2,
                "factures_traitees": 2,
                "alertes_generees": 1,
                "alertes_en_attente": 0,
                "alertes_traitees": 1,
                "alertes_escaladees": 0,
                "montant_reclame": 100,
                "montant_rembourse": 50,
                "montant_a_risque": 100,
                "montant_economise": 50,
                "fraudes_confirmees": 1,
                "alertes_decidees": 1,
                "latence_p50_ms": 10,
                "latence_p95_ms": 15,
            })
        if "AS JOUR" in query:
            return _Result(rows=[{"jour": "2026-10-21", "factures": 2,
                                  "alertes": 1, "montant_economise": 50}])
        if "GROUP BY PRESTATAIRE_ID" in query:
            return _Result(rows=[])
        if "WIDTH_BUCKET" in query:
            return _Result(rows=[])
        if "SELECT THRESHOLD" in query:
            return _Result({"threshold": 0.8})
        if "JSONB_ARRAY_ELEMENTS_TEXT" in query:
            return _Result(rows=[])
        if "ETAT_NOTIFICATION AS ETAT" in query:
            return _Result(rows=[])
        if "TOKENS_IN" in query:
            return _Result({
                "tokens_entree": 0,
                "tokens_sortie": 0,
                "taux_cache_hit": None,
                "latence_p50_ms": None,
                "latence_p95_ms": None,
            })
        raise AssertionError(f"Unexpected query: {query}")


class _Result:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


def test_dashboard_kpis_read_current_tables_instead_of_snapshot():
    conn = LiveBiConnection()

    result = _compute_kpis(conn, 30)

    assert result["factures_enregistrees"] == 2
    assert result["alertes_en_attente"] == 0
    assert result["stale"] is False
    assert result["date_rafraichissement"] is not None
    assert all("MV_BI_FACTURES" not in query for query in conn.queries)
    dashboard_queries = [query for query in conn.queries if "FROM DASHBOARD" in query]
    assert dashboard_queries
    assert all("LATEST_DECISION" in query and "FROM FACTURES F" in query
               for query in dashboard_queries)
    assert all("DATE_ACTIVITE >= CURRENT_DATE" in query for query in dashboard_queries
               if "INTERVAL '1 DAY'" in query)
    assert any(
        "GREATEST(" in query
        and "P.DATE::DATE" in query
        and "D.DATE_DECISION::DATE" in query
        for query in dashboard_queries
    )
