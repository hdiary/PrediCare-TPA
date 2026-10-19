"""Create the five-minute BI snapshot consumed by Metabase and the API."""
from alembic import op


revision = "0016_bi_materialized_snapshot"
down_revision = "0015_phase6_alert_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE MATERIALIZED VIEW IF NOT EXISTS mv_bi_factures AS
    SELECT * FROM v_bi_factures WITH NO DATA;
    """)
    op.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_bi_factures_facture_id
    ON mv_bi_factures (facture_id);
    """)
    op.execute("REFRESH MATERIALIZED VIEW mv_bi_factures;")
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'metabase_ro') THEN
            GRANT SELECT ON mv_bi_factures TO metabase_ro;
        END IF;
    END $$;
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_bi_factures;")
