"""Pool de connexions PostgreSQL (psycopg 3) et dépendance FastAPI."""
import logging
from collections.abc import Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from api.config import get_settings

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None


class DatabaseUnavailableError(Exception):
    """La base n'est pas joignable (convertie en HTTP 503)."""


def init_pool() -> None:
    """Crée le pool sans bloquer : il se reconnecte seul si la base tarde."""
    global _pool
    _pool = ConnectionPool(
        conninfo=get_settings().database_url,
        min_size=1,
        max_size=10,
        kwargs={"row_factory": dict_row},
        open=False,
    )
    _pool.open(wait=False)


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_pool() -> ConnectionPool | None:
    return _pool


def get_db() -> Iterator[psycopg.Connection]:
    """Dépendance FastAPI : une connexion par requête, validée à la sortie."""
    if _pool is None:
        raise DatabaseUnavailableError("pool non initialisé")
    try:
        with _pool.connection(timeout=5) as conn:
            yield conn
    except psycopg.OperationalError as exc:
        raise DatabaseUnavailableError(str(exc)) from exc
