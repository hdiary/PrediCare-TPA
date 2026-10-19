-- 040_alertes_prescription.sql (P3-16) : alertes issues des règles métier (prescription),
-- stockées à côté de l'explication SHAP. Une facture peut avoir 0..n alertes de règle.
-- Prérequis : 030_predictions_audit_decisions.sql

CREATE TABLE IF NOT EXISTS alertes_prescription (
    alerte_regle_id BIGSERIAL PRIMARY KEY,
    prediction_id   BIGINT NOT NULL REFERENCES predictions(prediction_id) ON DELETE CASCADE,
    facture_id      TEXT   NOT NULL REFERENCES factures(facture_id),
    regle_code      TEXT   NOT NULL,
    severite        TEXT   NOT NULL CHECK (severite IN ('info', 'moyenne', 'haute')),
    message         TEXT   NOT NULL,
    details         JSONB,
    cree_le         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_alertes_prescription_facture ON alertes_prescription (facture_id);
CREATE INDEX IF NOT EXISTS idx_alertes_prescription_regle   ON alertes_prescription (regle_code, cree_le);

-- Paramètre modifiable en direct pour la règle de quantité (voir api/services/rules.py)
INSERT INTO configuration (cle, valeur) VALUES ('regle_quantite_max_medicament', '10')
ON CONFLICT (cle) DO NOTHING;
