"""Autorise la connexion des rôles applicatifs (app_rw, identity_reader, agent_ro).

Revision ID: 0006_login_roles
Revises: 0005_api_tables

p1_0003 crée ces rôles en NOLOGIN (rôles de groupe), mais docker-compose fait
connecter l'API avec `app_rw:<mot de passe>@db` et l'agent avec `agent_ro:...`.
Sans LOGIN ni mot de passe, l'API ne peut pas se connecter à la base.

Les mots de passe viennent des variables d'environnement du service loader
(DB_APP_RW_PASSWORD, DB_IDENTITY_READER_PASSWORD, DB_AGENT_RO_PASSWORD), jamais du code.
Si une variable est absente, le rôle reste en NOLOGIN (ex. : tests, CI).
Les mots de passe sont appliqués à l'exécution de la migration : pour les changer plus
tard, utiliser ALTER ROLE ou refaire un `docker compose down -v`.
"""
import os

from alembic import op

revision = "0006_login_roles"
down_revision = "0005_api_tables"
branch_labels = None
depends_on = None

ROLE_PASSWORD_ENV = {
    "app_rw": "DB_APP_RW_PASSWORD",
    "identity_reader": "DB_IDENTITY_READER_PASSWORD",
    "agent_ro": "DB_AGENT_RO_PASSWORD",
}

# quote_literal / quote_ident : le mot de passe n'est jamais collé dans le SQL
APPLY_SQL = """
DO $$
BEGIN
    EXECUTE 'ALTER ROLE ' || quote_ident(current_setting('app.role_name'))
         || ' LOGIN PASSWORD ' || quote_literal(current_setting('app.role_pwd'));
END $$;
"""


def upgrade() -> None:
    bind = op.get_bind()
    for role, env_var in ROLE_PASSWORD_ENV.items():
        password = os.environ.get(env_var)
        if not password:
            print(f"[0006] {env_var} absent : {role} reste en NOLOGIN")
            continue
        bind.exec_driver_sql("SELECT set_config('app.role_name', %s, true)", (role,))
        bind.exec_driver_sql("SELECT set_config('app.role_pwd', %s, true)", (password,))
        bind.exec_driver_sql(APPLY_SQL)


def downgrade() -> None:
    bind = op.get_bind()
    for role in ROLE_PASSWORD_ENV:
        bind.exec_driver_sql(f"ALTER ROLE {role} NOLOGIN PASSWORD NULL")
