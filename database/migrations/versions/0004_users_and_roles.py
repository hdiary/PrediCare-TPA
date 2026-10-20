"""Créer les utilisateurs, rôles et attributions utilisateur-rôle de l'application.

ID de révision : 0004_users_and_roles
Révise : 0003_foreign_keys
"""
from alembic import op

revision = "0004_users_and_roles"
down_revision = "0003_foreign_keys"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE roles (
        role_id      BIGSERIAL PRIMARY KEY,
        nom_role     TEXT NOT NULL CHECK (btrim(nom_role) <> ''),
        description  TEXT,
        cree_le      TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE UNIQUE INDEX uq_roles_nom_role_lower
        ON roles (lower(nom_role));
    INSERT INTO roles (nom_role, description) VALUES
        ('professionnel_sante', 'Professionnel de santé'),
        ('assure', 'Assuré'),
        ('gestionnaire', 'Gestionnaire'),
        ('administrateur', 'Administrateur');

    CREATE TABLE utilisateurs (
        utilisateur_id     BIGSERIAL PRIMARY KEY,
        nom_utilisateur    TEXT NOT NULL CHECK (btrim(nom_utilisateur) <> ''),
        hash_mot_de_passe  TEXT NOT NULL CHECK (btrim(hash_mot_de_passe) <> ''),
        est_actif          BOOLEAN NOT NULL DEFAULT TRUE,
        cree_le            TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE UNIQUE INDEX uq_utilisateurs_nom_utilisateur_lower
        ON utilisateurs (lower(nom_utilisateur));

    CREATE TABLE utilisateurs_roles (
        utilisateur_id  BIGINT NOT NULL
                        REFERENCES utilisateurs(utilisateur_id) ON DELETE CASCADE,
        role_id         BIGINT NOT NULL
                        REFERENCES roles(role_id) ON DELETE CASCADE,
        attribue_le     TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (utilisateur_id, role_id)
    );
    CREATE INDEX ix_utilisateurs_roles_role_id ON utilisateurs_roles(role_id);
    CREATE UNIQUE INDEX uq_utilisateurs_roles_utilisateur_id
        ON utilisateurs_roles(utilisateur_id);
    """)


def downgrade():
    op.execute("""
    DROP TABLE IF EXISTS utilisateurs_roles;
    DROP TABLE IF EXISTS utilisateurs;
    DROP TABLE IF EXISTS roles;
    """)