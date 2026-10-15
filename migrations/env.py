"""Alembic environment: reads DATABASE_URL, runs raw-SQL migrations."""
import os

from alembic import context
from sqlalchemy import create_engine, pool


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set "
                           "(e.g. postgresql://user:pass@db:5432/predicare)")
    # psycopg 3 driver
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def run_migrations_online() -> None:
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None,
                          transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("offline mode is not supported (raw SQL migrations)")
run_migrations_online()
