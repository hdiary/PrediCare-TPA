"""Align the shared BI snapshot with the API and track refresh health."""
from alembic import op


revision = "0018_bi_snapshot_unification"
down_revision = "0017_consolidate_migration_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    prediction_columns = {
        row[0]
        for row in bind.exec_driver_sql(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'predictions'
            """
        )
    }
    prediction_date = "created_at" if "created_at" in prediction_columns else "date"
    prediction_threshold = "threshold" if "threshold" in prediction_columns else "seuil_utilise"
    op.execute("ALTER TABLE predictions ADD COLUMN IF NOT EXISTS latence_ms INTEGER")
    op.execute("""
    DROP MATERIALIZED VIEW IF EXISTS mv_bi_factures;
    """)
    op.execute(f"""
    CREATE MATERIALIZED VIEW mv_bi_factures AS
    SELECT v.*,
           f.montant_pris_en_charge,
           c.montant_reclame,
           c.montant_calcule,
           latency.prediction_id,
           latency.latence_ms,
           latency.threshold
    FROM v_bi_factures v
    JOIN factures f USING (facture_id)
    LEFT JOIN calculs_remboursement c USING (facture_id)
    LEFT JOIN LATERAL (
        SELECT p.prediction_id, p.latence_ms, p.{prediction_threshold} AS threshold
        FROM predictions p
        WHERE p.facture_id = v.facture_id
        ORDER BY p.{prediction_date} DESC, p.prediction_id DESC
        LIMIT 1
    ) latency ON TRUE;
    """)
    op.execute("""
    CREATE UNIQUE INDEX ux_mv_bi_factures_facture_id
        ON mv_bi_factures (facture_id);
    CREATE TABLE IF NOT EXISTS bi_refresh_status (
        singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
        last_success_at TIMESTAMPTZ,
        last_error TEXT
    );
    INSERT INTO bi_refresh_status (singleton, last_success_at)
    VALUES (TRUE, now())
    ON CONFLICT (singleton) DO NOTHING;

    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
            GRANT SELECT ON mv_bi_factures, bi_refresh_status TO app_rw;
            IF to_regclass('rag_query_log') IS NOT NULL THEN
                GRANT SELECT ON rag_query_log TO app_rw;
            END IF;
        END IF;
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'metabase_ro') THEN
            GRANT SELECT ON mv_bi_factures TO metabase_ro;
        END IF;
    END $$;
    """)


def downgrade() -> None:
    op.execute("""
    DROP MATERIALIZED VIEW IF EXISTS mv_bi_factures;
    DROP TABLE IF EXISTS bi_refresh_status;

    CREATE MATERIALIZED VIEW mv_bi_factures AS
    SELECT * FROM v_bi_factures;
    CREATE UNIQUE INDEX ux_mv_bi_factures_facture_id
        ON mv_bi_factures (facture_id);
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
            GRANT SELECT ON mv_bi_factures TO app_rw;
        END IF;
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'metabase_ro') THEN
            GRANT SELECT ON mv_bi_factures TO metabase_ro;
        END IF;
    END $$;
    """)
