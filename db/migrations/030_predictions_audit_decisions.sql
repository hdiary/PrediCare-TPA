-- 030_predictions_audit_decisions.sql
-- Tables de P2 (predictions, explications_shap, decisions_gestionnaire) et de P3 (journal_audit).
-- À CONFIRMER avec P2 : qui crée ces trois tables ? (l'API les écrit dans /predict et /alerts).
-- Si P2 les a déjà créées, comparer les colonnes avec api/repositories.py :
-- CREATE TABLE IF NOT EXISTS ne modifie pas une table existante.

CREATE TABLE IF NOT EXISTS predictions (
    prediction_id  BIGSERIAL PRIMARY KEY,
    facture_id     TEXT NOT NULL UNIQUE REFERENCES factures(facture_id),  -- une prédiction par facture
    nom_modele     TEXT NOT NULL,
    version_modele TEXT NOT NULL,            -- version MLflow
    score          REAL NOT NULL CHECK (score BETWEEN 0 AND 1),
    seuil_utilise  REAL NOT NULL,
    est_alerte     BOOLEAN NOT NULL,
    latence_ms     INT,
    variables      JSONB,                    -- entrées du modèle (suivi de dérive)
    soumis_par     BIGINT REFERENCES utilisateurs(utilisateur_id),
    date           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions (date);
CREATE INDEX IF NOT EXISTS idx_predictions_alerte ON predictions (est_alerte, date);

CREATE TABLE IF NOT EXISTS explications_shap (
    prediction_id BIGINT PRIMARY KEY REFERENCES predictions(prediction_id) ON DELETE CASCADE,
    facture_id    TEXT NOT NULL REFERENCES factures(facture_id),
    valeurs       JSONB NOT NULL   -- {"valeur_base": x, "top": [{variable, valeur, contribution}], "toutes": {...}}
);

CREATE TABLE IF NOT EXISTS decisions_gestionnaire (
    decision_id      BIGSERIAL PRIMARY KEY,
    prediction_id    BIGINT NOT NULL REFERENCES predictions(prediction_id) ON DELETE CASCADE,
    facture_id       TEXT NOT NULL REFERENCES factures(facture_id),
    gestionnaire_id  BIGINT NOT NULL REFERENCES utilisateurs(utilisateur_id),  -- toujours un humain
    decision         TEXT NOT NULL CHECK (decision IN
                       ('fraude_confirmee', 'faux_positif', 'a_investiguer')),
    commentaire      TEXT,
    montant_economise BIGINT CHECK (montant_economise IS NULL OR montant_economise >= 0),  -- MGA
    date_decision    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_decisions_prediction ON decisions_gestionnaire (prediction_id, date_decision);

-- Journal d'audit (AI Act art. 12) : ajout seul
CREATE TABLE IF NOT EXISTS journal_audit (
    audit_id       BIGSERIAL PRIMARY KEY,
    horodatage     TIMESTAMPTZ NOT NULL DEFAULT now(),
    type_evenement TEXT NOT NULL,   -- prediction | decision | facture_rejetee | erreur_prediction | modele_charge | acces_identite
    utilisateur_id BIGINT,
    type_entite    TEXT NOT NULL,
    entite_id      TEXT,
    nom_modele     TEXT,
    version_modele TEXT,
    entree         JSONB,
    sortie         JSONB
);
CREATE INDEX IF NOT EXISTS idx_audit_horodatage ON journal_audit (horodatage);
CREATE INDEX IF NOT EXISTS idx_audit_type ON journal_audit (type_evenement, horodatage);
CREATE INDEX IF NOT EXISTS idx_audit_entite ON journal_audit (type_entite, entite_id);

CREATE OR REPLACE FUNCTION journal_audit_immuable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'journal_audit est en ajout seul (pas de UPDATE / DELETE / TRUNCATE)';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_pas_de_modif ON journal_audit;
CREATE TRIGGER trg_audit_pas_de_modif BEFORE UPDATE OR DELETE ON journal_audit
    FOR EACH ROW EXECUTE FUNCTION journal_audit_immuable();

DROP TRIGGER IF EXISTS trg_audit_pas_de_truncate ON journal_audit;
CREATE TRIGGER trg_audit_pas_de_truncate BEFORE TRUNCATE ON journal_audit
    FOR EACH STATEMENT EXECUTE FUNCTION journal_audit_immuable();
