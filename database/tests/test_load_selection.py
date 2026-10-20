from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from load import OPERATIONAL_TABLES, check_counts, selected_sources


def test_default_loader_skips_operational_records():
    selected_tables = {source.table for source in selected_sources()}

    assert selected_tables.isdisjoint(OPERATIONAL_TABLES)
    assert {
        "factures", "lignes_facture", "ordonnances", "ordonnance_lignes"
    } <= OPERATIONAL_TABLES


def test_archive_import_can_include_operational_records():
    selected_tables = {
        source.table for source in selected_sources(include_operational_data=True)
    }

    assert OPERATIONAL_TABLES <= selected_tables


class CountResult:
    def __init__(self, count):
        self.count = count

    def fetchone(self):
        return (self.count,)


class CountConnection:
    def __init__(self, count):
        self.count = count

    def execute(self, _query):
        return CountResult(self.count)


def test_count_check_allows_preexisting_database_rows():
    assert check_counts(
        CountConnection(84596),
        [{"table": "factures", "rows": 84593}],
    ) == []


def test_count_check_detects_missing_source_rows():
    assert check_counts(
        CountConnection(84592),
        [{"table": "factures", "rows": 84593}],
    ) == ["factures: file has 84593 rows, database has only 84592"]
