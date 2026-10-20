"""Converge existing API databases on the username and role-assignment schema."""
from alembic import op


revision = "0019_normalize_user_roles"
down_revision = "0018_bi_snapshot_unification"
branch_labels = None
depends_on = None


UPGRADE_SQL = """
DO $$
DECLARE
    has_legacy_role BOOLEAN;
    has_legacy_email BOOLEAN;
    r RECORD;
BEGIN
    ALTER TABLE roles ADD COLUMN IF NOT EXISTS role_id BIGSERIAL;
    ALTER TABLE roles ADD COLUMN IF NOT EXISTS nom_role TEXT;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'roles' AND column_name = 'code'
    ) THEN
        UPDATE roles SET nom_role = code WHERE nom_role IS NULL;
        EXECUTE $sql$
            INSERT INTO roles (code, libelle, nom_role)
            VALUES
                ('professionnel_sante', 'Professionnel de santé', 'professionnel_sante'),
                ('assure', 'Assuré', 'assure'),
                ('gestionnaire', 'Gestionnaire', 'gestionnaire'),
                ('administrateur', 'Administrateur', 'administrateur')
            ON CONFLICT (code) DO NOTHING
        $sql$;
    ELSE
        INSERT INTO roles (nom_role, description)
        VALUES
            ('professionnel_sante', 'Professionnel de santé'),
            ('assure', 'Assuré'),
            ('gestionnaire', 'Gestionnaire'),
            ('administrateur', 'Administrateur')
        ON CONFLICT DO NOTHING;
    END IF;

    CREATE UNIQUE INDEX IF NOT EXISTS uq_roles_role_id ON roles(role_id);
    CREATE UNIQUE INDEX IF NOT EXISTS uq_roles_nom_role_lower ON roles(lower(nom_role));

    has_legacy_role := EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'utilisateurs' AND column_name = 'role'
    );
    has_legacy_email := EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'utilisateurs' AND column_name = 'email'
    );

    IF has_legacy_email AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'utilisateurs' AND column_name = 'nom_utilisateur'
    ) THEN
        FOR r IN
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'utilisateurs'::regclass AND contype = 'c'
              AND position('email' IN lower(pg_get_constraintdef(oid))) > 0
        LOOP
            EXECUTE 'ALTER TABLE utilisateurs DROP CONSTRAINT '
                || quote_ident(r.conname);
        END LOOP;
        ALTER TABLE utilisateurs RENAME COLUMN email TO nom_utilisateur;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'utilisateurs' AND column_name = 'mot_de_passe_hash'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'utilisateurs' AND column_name = 'hash_mot_de_passe'
    ) THEN
        ALTER TABLE utilisateurs RENAME COLUMN mot_de_passe_hash TO hash_mot_de_passe;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'utilisateurs' AND column_name = 'actif'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'utilisateurs' AND column_name = 'est_actif'
    ) THEN
        ALTER TABLE utilisateurs RENAME COLUMN actif TO est_actif;
    END IF;

    ALTER TABLE utilisateurs
        ADD COLUMN IF NOT EXISTS assure_id TEXT REFERENCES assures(assure_id),
        ADD COLUMN IF NOT EXISTS prestataire_id TEXT REFERENCES prestataires(prestataire_id),
        ADD COLUMN IF NOT EXISTS derniere_connexion TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS tentatives_echouees INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS verrouille_jusqua TIMESTAMPTZ;

    CREATE TABLE IF NOT EXISTS utilisateurs_roles (
        utilisateur_id BIGINT NOT NULL REFERENCES utilisateurs(utilisateur_id) ON DELETE CASCADE,
        role_id BIGINT NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
        attribue_le TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (utilisateur_id, role_id)
    );

    IF has_legacy_role THEN
        INSERT INTO utilisateurs_roles (utilisateur_id, role_id)
        SELECT u.utilisateur_id, r.role_id
        FROM utilisateurs u
        JOIN roles r ON lower(r.nom_role) = lower(u.role)
        ON CONFLICT (utilisateur_id, role_id) DO NOTHING;
        ALTER TABLE utilisateurs DROP COLUMN role CASCADE;
    END IF;

    CREATE UNIQUE INDEX IF NOT EXISTS uq_utilisateurs_nom_utilisateur_lower
        ON utilisateurs(lower(nom_utilisateur));
    CREATE UNIQUE INDEX IF NOT EXISTS uq_utilisateurs_roles_utilisateur_id
        ON utilisateurs_roles(utilisateur_id);

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
        GRANT SELECT ON roles TO app_rw;
        GRANT SELECT, INSERT, UPDATE ON utilisateurs TO app_rw;
        GRANT SELECT, INSERT, UPDATE, DELETE ON utilisateurs_roles TO app_rw;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_rw;
    END IF;
END $$;
"""


def upgrade() -> None:
    op.get_bind().exec_driver_sql(UPGRADE_SQL)


def downgrade() -> None:
    raise RuntimeError("La migration de normalisation des comptes n'est pas réversible.")
