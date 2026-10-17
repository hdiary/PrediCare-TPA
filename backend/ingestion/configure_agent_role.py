"""Provision the RAG agent's dedicated login with only agent_ro membership."""
import os

import psycopg
from psycopg import sql


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    password = os.environ.get("DB_AGENT_RO_PASSWORD")
    if not database_url or not password:
        raise RuntimeError("DATABASE_URL and DB_AGENT_RO_PASSWORD are required")

    with psycopg.connect(database_url) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", ("agent_login",)
        )
        if cursor.fetchone() is None:
            cursor.execute(
                sql.SQL(
                    "CREATE ROLE {} WITH LOGIN INHERIT NOSUPERUSER "
                    "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS "
                    "PASSWORD {}"
                ).format(sql.Identifier("agent_login"), sql.Literal(password))
            )
        else:
            cursor.execute(
                sql.SQL(
                    "ALTER ROLE {} WITH LOGIN INHERIT NOSUPERUSER "
                    "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS "
                    "PASSWORD {}"
                ).format(sql.Identifier("agent_login"), sql.Literal(password))
            )
        cursor.execute("GRANT agent_ro TO agent_login")
        connection.commit()

    print("[db-init] configured least-privilege agent login.")


if __name__ == "__main__":
    main()
