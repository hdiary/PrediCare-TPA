BEGIN;

CREATE TEMP VIEW v_bi_factures AS
SELECT *
FROM (VALUES
    ('FAC-1', DATE '2026-01-01', 'PRE-1', 'Prestataire 1', 100::numeric,
     'MGA', TRUE, TRUE, TRUE, 'rejete'::text),
    ('FAC-2', DATE '2026-01-02', 'PRE-2', 'Prestataire 2', 50::numeric,
     'MGA', FALSE, TRUE, TRUE, NULL::text),
    ('FAC-3', DATE '2026-01-03', 'PRE-1', 'Prestataire 1', 25::numeric,
     'MGA', TRUE, FALSE, TRUE, 'rejete'::text),
    ('FAC-4', DATE '2026-01-04', 'PRE-3', 'Prestataire 3', 20::numeric,
     'MGA', TRUE, FALSE, TRUE, 'valide'::text),
    ('FAC-5', DATE '2026-01-05', 'PRE-4', 'Prestataire 4', 999::numeric,
     'USD', TRUE, FALSE, FALSE, 'rejete'::text),
    ('FAC-6', DATE '2026-01-06', 'PRE-5', 'Prestataire 5', 30::numeric,
     'MGA', NULL::boolean, TRUE, TRUE, NULL::text)
) AS sample(
    facture_id, date_facture, prestataire_id, prestataire_nom, montant_total,
    devise, is_alert, est_fraude, est_valide, decision
);

DO $$
DECLARE
    recall_pct NUMERIC;
    rejection_pct NUMERIC;
    rejected_amount_mga NUMERIC;
    monthly_total_mga NUMERIC;
    monthly_alerted_mga NUMERIC;
    scoring_coverage_pct NUMERIC;
BEGIN
    SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE v.is_alert)
                 / NULLIF(COUNT(*), 0), 1)
      INTO recall_pct
      FROM v_bi_factures v
     WHERE v.est_fraude AND v.est_valide AND v.is_alert IS NOT NULL;

    SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE v.decision = 'rejete')
                 / NULLIF(COUNT(*), 0), 1)
      INTO rejection_pct
      FROM v_bi_factures v
     WHERE v.is_alert AND v.decision IN ('valide', 'rejete');

    SELECT COALESCE(SUM(v.montant_total), 0)
      INTO rejected_amount_mga
      FROM v_bi_factures v
     WHERE v.is_alert AND v.decision = 'rejete' AND v.devise = 'MGA';

    SELECT SUM(v.montant_total),
           SUM(v.montant_total) FILTER (WHERE v.is_alert)
      INTO monthly_total_mga, monthly_alerted_mga
      FROM v_bi_factures v
     WHERE v.devise = 'MGA';

    SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE v.is_alert IS NOT NULL)
                 / NULLIF(COUNT(*), 0), 3)
      INTO scoring_coverage_pct
      FROM v_bi_factures v;

    IF recall_pct IS DISTINCT FROM 50.0 THEN
        RAISE EXCEPTION 'Expected labelled-fraud recall 50.0%%, got %', recall_pct;
    END IF;
    IF rejection_pct IS DISTINCT FROM 75.0 THEN
        RAISE EXCEPTION 'Expected decided-alert rejection rate 75.0%%, got %', rejection_pct;
    END IF;
    IF rejected_amount_mga IS DISTINCT FROM 125 THEN
        RAISE EXCEPTION 'Expected rejected billed amount 125 MGA, got %', rejected_amount_mga;
    END IF;
    IF monthly_total_mga IS DISTINCT FROM 225 OR monthly_alerted_mga IS DISTINCT FROM 145 THEN
        RAISE EXCEPTION 'Unexpected MGA totals: billed %, alerted %',
            monthly_total_mga, monthly_alerted_mga;
    END IF;
    IF scoring_coverage_pct IS DISTINCT FROM 83.333 THEN
        RAISE EXCEPTION 'Expected scoring coverage 83.333%%, got %',
            scoring_coverage_pct;
    END IF;
END
$$;

ROLLBACK;
