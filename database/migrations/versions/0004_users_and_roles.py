"""Create application users, roles, and user-role assignments.

Revision ID: 0004_users_and_roles
Revises: 0003_foreign_keys
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
        role_name    TEXT NOT NULL CHECK (btrim(role_name) <> ''),
        description  TEXT,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE UNIQUE INDEX uq_roles_role_name_lower
        ON roles (lower(role_name));

    CREATE TABLE users (
        user_id       BIGSERIAL PRIMARY KEY,
        username      TEXT NOT NULL CHECK (btrim(username) <> ''),
        password_hash TEXT NOT NULL CHECK (btrim(password_hash) <> ''),
        is_active     BOOLEAN NOT NULL DEFAULT TRUE,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE UNIQUE INDEX uq_users_username_lower
        ON users (lower(username));

    CREATE TABLE user_roles (
        user_id     BIGINT NOT NULL
                    REFERENCES users(user_id) ON DELETE CASCADE,
        role_id     BIGINT NOT NULL
                    REFERENCES roles(role_id) ON DELETE CASCADE,
        assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (user_id, role_id)
    );
    CREATE INDEX ix_user_roles_role_id ON user_roles(role_id);
    """)


def downgrade():
    op.execute("""
    DROP TABLE IF EXISTS user_roles;
    DROP TABLE IF EXISTS users;
    DROP TABLE IF EXISTS roles;
    """)
