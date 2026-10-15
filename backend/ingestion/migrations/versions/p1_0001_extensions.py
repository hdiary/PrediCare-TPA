"""P1 0001 - extensions and schema_info

pgcrypto is always created. pgvector is created when PGVECTOR_REQUIRED is not
'0' (default: required, so a missing pgvector fails loudly instead of letting
P4 discover it later). Set PGVECTOR_REQUIRED=0 only for local tests on a
Postgres without pgvector.

Revision ID: p1_0001
Revises:
"""
import os

from alembic import op

revision = "p1_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    if os.environ.get("PGVECTOR_REQUIRED", "1") != "0":
        bind.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
    bind.exec_driver_sql("""
        CREATE TABLE schema_info (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )""")
    bind.exec_driver_sql("""
        INSERT INTO schema_info (key, value) VALUES
            ('contract_version', 'v0.1'),
            ('owner', 'P1')""")


def downgrade() -> None:
    # extensions are left in place: other members' tables may use them
    op.get_bind().exec_driver_sql("DROP TABLE IF EXISTS schema_info")
