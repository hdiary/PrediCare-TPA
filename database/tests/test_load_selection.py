from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from load import OPERATIONAL_TABLES, selected_sources


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
