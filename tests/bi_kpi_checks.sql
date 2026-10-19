BEGIN;

CREATE TEMP VIEW v_bi_factures AS
SELECT *
FROM (VALUES
    ('FAC-1', DATE '2026-01-01', 100::numeric, TRUE, 'CONFIRMER_FRAUDE'::text, 100::numeric, 60::numeric),
    ('FAC-2', DATE '2026-01-02', 50::numeric, FALSE, NULL::text, 50::numeric, 40::numeric),
    ('FAC-3', DATE '2026-01-03', 25::numeric, TRUE, 'REJETER'::text, 25::numeric, 10::numeric),
    ('FAC-4', DATE '2026-01-04', 20::numeric, TRUE, 'VALIDER'::text, 20::numeric, 20::numeric),
    ('FAC-5', DATE '2026-01-05', 999::numeric, TRUE, NULL::text, 999::numeric, 900::numeric),
    ('FAC-6', DATE '2026-01-06', 30::numeric, NULL::boolean, NULL::text, 30::numeric, 30::numeric)
) AS sample(
    facture_id, date_facture, montant_total, is_alert, decision,
    montant_reclame, montant_calcule
);

DO $$
DECLARE
    alert_rate NUMERIC;
    precision_pct NUMERIC;
    risk_amount NUMERIC;
    saved_amount NUMERIC;
BEGIN
    SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE is_alert)
                 / NULLIF(COUNT(*) FILTER (WHERE is_alert IS NOT NULL), 0), 1)
      INTO alert_rate
      FROM v_bi_factures;

    SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE decision = 'CONFIRMER_FRAUDE')
                 / NULLIF(COUNT(*) FILTER (WHERE decision IS NOT NULL), 0), 1)
      INTO precision_pct
      FROM v_bi_factures
     WHERE is_alert;

    SELECT COALESCE(SUM(montant_total) FILTER (WHERE is_alert), 0),
           COALESCE(SUM(montant_reclame - montant_calcule)
                    FILTER (WHERE decision IN ('REJETER', 'CONFIRMER_FRAUDE')), 0)
      INTO risk_amount, saved_amount
      FROM v_bi_factures;

    IF alert_rate IS DISTINCT FROM 80.0 THEN
        RAISE EXCEPTION 'Expected alert rate 80.0%%, got %', alert_rate;
    END IF;
    IF precision_pct IS DISTINCT FROM 33.3 THEN
        RAISE EXCEPTION 'Expected operational precision 33.3%%, got %', precision_pct;
    END IF;
    IF risk_amount IS DISTINCT FROM 1144 THEN
        RAISE EXCEPTION 'Expected risk amount 1144, got %', risk_amount;
    END IF;
    IF saved_amount IS DISTINCT FROM 55 THEN
        RAISE EXCEPTION 'Expected saved amount 55, got %', saved_amount;
    END IF;
END
$$;

ROLLBACK;
