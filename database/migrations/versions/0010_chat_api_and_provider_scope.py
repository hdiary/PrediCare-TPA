"""Add authenticated chat history and provider-scoped RAG access.

Revision ID: 0010_chat_api_and_provider_scope
Revises: 0009_bi_decision_alignment, 0004_users_and_roles, 0006_login_roles
"""
from alembic import op


revision = "0010_chat_api_and_provider_scope"
down_revision = ("0009_bi_decision_alignment", "0004_users_and_roles", "0006_login_roles")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS utilisateurs (
        utilisateur_id      BIGSERIAL PRIMARY KEY,
        email               TEXT NOT NULL UNIQUE CHECK (email = lower(email)),
        mot_de_passe_hash   TEXT NOT NULL,
        role                TEXT NOT NULL CHECK (role IN (
            'professionnel_sante', 'assure', 'gestionnaire', 'administrateur'
        )),
        assure_id           TEXT REFERENCES assures(assure_id),
        prestataire_id      TEXT REFERENCES prestataires(prestataire_id),
        actif               BOOLEAN NOT NULL DEFAULT TRUE,
        cree_le             TIMESTAMPTZ NOT NULL DEFAULT now(),
        derniere_connexion  TIMESTAMPTZ,
        tentatives_echouees INTEGER NOT NULL DEFAULT 0,
        verrouille_jusqua   TIMESTAMPTZ
    );

    CREATE TABLE IF NOT EXISTS configuration (
        cle            TEXT PRIMARY KEY,
        valeur         TEXT NOT NULL,
        mis_a_jour_le  TIMESTAMPTZ NOT NULL DEFAULT now(),
        mis_a_jour_par TEXT
    );
    INSERT INTO configuration (cle, valeur) VALUES
        ('seuil_alerte', '0.8'),
        ('notif_slack', 'true'),
        ('notif_email', 'true'),
        ('notif_email_destinataire', 'gestionnaire@predicare.local')
    ON CONFLICT (cle) DO NOTHING;

    CREATE TABLE chat_conversations (
        id          UUID PRIMARY KEY,
        user_id     BIGINT NOT NULL REFERENCES utilisateurs(utilisateur_id)
                    ON DELETE CASCADE,
        title       TEXT NOT NULL,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_chat_conversations_user_updated
        ON chat_conversations(user_id, updated_at DESC);

    CREATE TABLE chat_messages (
        id              UUID PRIMARY KEY,
        conversation_id UUID NOT NULL REFERENCES chat_conversations(id)
                        ON DELETE CASCADE,
        role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
        content         TEXT NOT NULL,
        sources         JSONB NOT NULL DEFAULT '[]'::jsonb,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_chat_messages_conversation_created
        ON chat_messages(conversation_id, created_at, id);

    GRANT SELECT, INSERT, UPDATE, DELETE ON utilisateurs, configuration,
        chat_conversations, chat_messages TO app_rw;
    GRANT USAGE, SELECT ON SEQUENCE utilisateurs_utilisateur_id_seq TO app_rw;

    CREATE OR REPLACE VIEW v_agent_claim_status AS
        SELECT assure_id, contrat_id, facture_id, date_reception, date_soin,
               date_traitement, type_facture, statut, montant_total,
               montant_pris_en_charge, prestataire_id
        FROM factures;
    REVOKE ALL ON v_agent_claim_status FROM PUBLIC;
    GRANT SELECT ON v_agent_claim_status TO agent_ro;
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS chat_messages;
    DROP TABLE IF EXISTS chat_conversations;
    CREATE OR REPLACE VIEW v_agent_claim_status AS
        SELECT assure_id, contrat_id, facture_id, date_reception, date_soin,
               date_traitement, type_facture, statut, montant_total,
               montant_pris_en_charge
        FROM factures;
    REVOKE ALL ON v_agent_claim_status FROM PUBLIC;
    GRANT SELECT ON v_agent_claim_status TO agent_ro;
    """)
