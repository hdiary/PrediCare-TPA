"""Tables utilisées par l'API (alignement sur le code de backend/api).

Revision ID: 0005_api_tables
Revises: 0004_users_and_roles

Pourquoi cette migration
------------------------
Le code de l'API lit et écrit dans `utilisateurs`, `roles(code)`, `configuration`,
`predictions` (colonnes est_alerte, seuil_utilise...), `explications_shap`,
`decisions_gestionnaire`, `journal_audit` et `alertes_prescription`. Ces tables
n'étaient définies que dans database/sql/*.sql, que personne n'exécutait, alors que
les migrations 0002 et 0004 créaient d'autres tables (users, user_roles, roles(role_id),
shap_explanations, decisions_gestionnaires, audit_log) que l'API n'utilise pas.

Cette migration :
  1. supprime les tables inutilisées créées par 0002 et 0004 ;
  2. crée les tables attendues par l'API (contenu de database/sql/020, 030 et 040) ;
  3. donne à app_rw le strict nécessaire sur ces tables.

`documents_vectorises` (RAG, créée par 0002) est conservée.

ATTENTION : la suppression des tables de 0002/0004 détruit leurs données. À n'appliquer
que sur une base dont ces tables sont vides. Le downgrade supprime les tables créées ici
sans recréer celles de 0002/0004 (elles étaient inutilisées).
"""
from alembic import op

revision = "0005_api_tables"
down_revision = "0004_users_and_roles"
branch_labels = None
depends_on = None

UPGRADE_SQL = """
-- 1. Tables de 0002 / 0004 que l'API n'utilise pas
DROP TABLE IF EXISTS decisions_gestionnaires, shap_explanations, predictions, audit_log CASCADE;
DROP FUNCTION IF EXISTS audit_log_immutable();
DROP TABLE IF EXISTS user_roles, users, roles CASCADE;

-- 2a. Rôles applicatifs, utilisateurs, configuration (database/sql/020)
CREATE TABLE roles (
    code    TEXT PRIMARY KEY,
    libelle TEXT NOT NULL
);
INSERT INTO roles (code, libelle) VALUES
    ('professionnel_sante', 'Professionnel de santé'),
    ('assure',              'Assuré'),
    ('gestionnaire',        'Gestionnaire'),
    ('administrateur',      'Administrateur');

CREATE TABLE utilisateurs (
    utilisateur_id      BIGSERIAL PRIMARY KEY,
    email               TEXT NOT NULL UNIQUE CHECK (email = lower(email)),
    mot_de_passe_hash   TEXT NOT NULL,
    role                TEXT NOT NULL REFERENCES roles(code),
    assure_id           TEXT REFERENCES assures(assure_id),
    prestataire_id      TEXT REFERENCES prestataires(prestataire_id),
    actif               BOOLEAN NOT NULL DEFAULT TRUE,
    cree_le             TIMESTAMPTZ NOT NULL DEFAULT now(),
    derniere_connexion  TIMESTAMPTZ,
    tentatives_echouees INT NOT NULL DEFAULT 0,
    verrouille_jusqua   TIMESTAMPTZ
);

CREATE TABLE configuration (
    cle            TEXT PRIMARY KEY,
    valeur         TEXT NOT NULL,
    mis_a_jour_le  TIMESTAMPTZ NOT NULL DEFAULT now(),
    mis_a_jour_par TEXT
);
INSERT INTO configuration (cle, valeur) VALUES
    ('seuil_alerte', '0.8'),
    ('notif_slack', 'true'),
    ('notif_email', 'true'),
    ('notif_email_destinataire', 'gestionnaire@predicare.local'),
    ('regle_quantite_max_medicament', '10');

-- 2b. Prédictions, explications, décisions, journal d'audit (database/sql/030)
CREATE TABLE predictions (
    prediction_id  BIGSERIAL PRIMARY KEY,
    facture_id     TEXT NOT NULL UNIQUE REFERENCES factures(facture_id),
    nom_modele     TEXT NOT NULL,
    version_modele TEXT NOT NULL,
    score          REAL NOT NULL CHECK (score BETWEEN 0 AND 1),
    seuil_utilise  REAL NOT NULL,
    est_alerte     BOOLEAN NOT NULL,
    latence_ms     INT,
    variables      JSONB,
    soumis_par     BIGINT REFERENCES utilisateurs(utilisateur_id),
    date           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_predictions_date ON predictions (date);
CREATE INDEX idx_predictions_alerte ON predictions (est_alerte, date);

CREATE TABLE explications_shap (
    prediction_id BIGINT PRIMARY KEY REFERENCES predictions(prediction_id) ON DELETE CASCADE,
    facture_id    TEXT NOT NULL REFERENCES factures(facture_id),
    valeurs       JSONB NOT NULL
);

CREATE TABLE decisions_gestionnaire (
    decision_id       BIGSERIAL PRIMARY KEY,
    prediction_id     BIGINT NOT NULL REFERENCES predictions(prediction_id) ON DELETE CASCADE,
    facture_id        TEXT NOT NULL REFERENCES factures(facture_id),
    gestionnaire_id   BIGINT NOT NULL REFERENCES utilisateurs(utilisateur_id),
    decision          TEXT NOT NULL CHECK (decision IN
                        ('fraude_confirmee', 'faux_positif', 'a_investiguer')),
    commentaire       TEXT,
    montant_economise BIGINT CHECK (montant_economise IS NULL OR montant_economise >= 0),
    date_decision     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_decisions_prediction ON decisions_gestionnaire (prediction_id, date_decision);

CREATE TABLE journal_audit (
    audit_id       BIGSERIAL PRIMARY KEY,
    horodatage     TIMESTAMPTZ NOT NULL DEFAULT now(),
    type_evenement TEXT NOT NULL,
    utilisateur_id BIGINT,
    type_entite    TEXT NOT NULL,
    entite_id      TEXT,
    nom_modele     TEXT,
    version_modele TEXT,
    entree         JSONB,
    sortie         JSONB
);
CREATE INDEX idx_audit_horodatage ON journal_audit (horodatage);
CREATE INDEX idx_audit_type ON journal_audit (type_evenement, horodatage);
CREATE INDEX idx_audit_entite ON journal_audit (type_entite, entite_id);

-- Ajout seul (AI Act art. 12) : ni UPDATE, ni DELETE, ni TRUNCATE
CREATE FUNCTION journal_audit_immuable() RETURNS trigger AS $fn$
BEGIN
    RAISE EXCEPTION 'journal_audit est en ajout seul (pas de UPDATE / DELETE / TRUNCATE)';
END;
$fn$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_pas_de_modif BEFORE UPDATE OR DELETE ON journal_audit
    FOR EACH ROW EXECUTE FUNCTION journal_audit_immuable();
CREATE TRIGGER trg_audit_pas_de_truncate BEFORE TRUNCATE ON journal_audit
    FOR EACH STATEMENT EXECUTE FUNCTION journal_audit_immuable();

-- 2c. Alertes issues des règles de prescription (database/sql/040)
CREATE TABLE alertes_prescription (
    alerte_regle_id BIGSERIAL PRIMARY KEY,
    prediction_id   BIGINT NOT NULL REFERENCES predictions(prediction_id) ON DELETE CASCADE,
    facture_id      TEXT   NOT NULL REFERENCES factures(facture_id),
    regle_code      TEXT   NOT NULL,
    severite        TEXT   NOT NULL CHECK (severite IN ('info', 'moyenne', 'haute')),
    message         TEXT   NOT NULL,
    details         JSONB,
    cree_le         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_alertes_prescription_facture ON alertes_prescription (facture_id);
CREATE INDEX idx_alertes_prescription_regle ON alertes_prescription (regle_code, cree_le);

-- 3. Droits (principe du moindre privilège) : seulement pour les rôles qui existent
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
        GRANT SELECT ON roles TO app_rw;
        GRANT SELECT, INSERT, UPDATE ON utilisateurs, configuration TO app_rw;
        GRANT SELECT, INSERT ON predictions, explications_shap, decisions_gestionnaire,
              journal_audit, alertes_prescription TO app_rw;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_rw;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ml_ro') THEN
        GRANT SELECT ON predictions, explications_shap TO ml_ro;
    END IF;
END $$;
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS alertes_prescription, journal_audit, decisions_gestionnaire,
                     explications_shap, predictions, configuration, utilisateurs, roles CASCADE;
DROP FUNCTION IF EXISTS journal_audit_immuable();
"""


def upgrade() -> None:
    op.get_bind().exec_driver_sql(UPGRADE_SQL)


def downgrade() -> None:
    op.get_bind().exec_driver_sql(DOWNGRADE_SQL)
