"""Création des comptes de démonstration au démarrage (idempotent)."""
import logging

import psycopg

from api.config import get_settings
from api.db import get_pool
from api.security import hash_password

logger = logging.getLogger(__name__)

DEMO_USERS = [
    ("pro@predicare.local", "professionnel_sante"),
    ("assure@predicare.local", "assure"),
    ("gestionnaire@predicare.local", "gestionnaire"),
    ("admin@predicare.local", "administrateur"),
]


def ensure_demo_users() -> None:
    """Ne fait rien si DEMO_PASSWORD est absent ; ne plante jamais le démarrage."""
    settings = get_settings()
    pool = get_pool()
    if not settings.demo_password or pool is None:
        logger.info("demo_users_skipped")
        return
    try:
        pwd_hash = hash_password(settings.demo_password)
        with pool.connection(timeout=10) as conn:
            for email, role in DEMO_USERS:
                insured = settings.demo_insured_id if role == "assure" else None
                provider = settings.demo_provider_id if role == "professionnel_sante" else None
                conn.execute(
                    "INSERT INTO users (email, password_hash, role, insured_id, provider_id) "
                    "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (email) DO NOTHING",
                    (email, pwd_hash, role, insured, provider),
                )
        logger.info("demo_users_ready")
    except psycopg.errors.UndefinedTable:
        logger.error("table 'users' absente : appliquer la migration db/migrations/020_users.sql")
    except Exception:  # noqa: BLE001
        logger.exception("demo_users_failed")
