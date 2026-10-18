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


def _pick(conn, query: str) -> str | None:
    row = conn.execute(query).fetchone()
    return next(iter(row.values())) if row else None


def ensure_demo_users() -> None:
    """Ne fait rien si DEMO_PASSWORD est absent ; ne plante jamais le démarrage.

    Le compte assuré est rattaché à un assuré principal ayant des factures ;
    le compte professionnel à un prestataire actif ayant des factures.
    """
    settings = get_settings()
    pool = get_pool()
    if not settings.demo_password or pool is None:
        logger.info("demo_users_skipped")
        return
    try:
        pwd_hash = hash_password(settings.demo_password)
        with pool.connection(timeout=10) as conn:
            assure_id = _pick(
                conn,
                "SELECT a.assure_id FROM assures a WHERE a.rang_beneficiaire = 'ASSURE_PRINCIPAL' "
                "AND EXISTS (SELECT 1 FROM factures f WHERE f.assure_id = a.assure_id) "
                "ORDER BY a.assure_id LIMIT 1",
            )
            prestataire_id = _pick(
                conn,
                "SELECT p.prestataire_id FROM prestataires p WHERE p.statut = 'ACTIF' "
                "AND EXISTS (SELECT 1 FROM factures f WHERE f.prestataire_id = p.prestataire_id) "
                "ORDER BY p.prestataire_id LIMIT 1",
            )
            for email, role in DEMO_USERS:
                conn.execute(
                    "INSERT INTO utilisateurs (email, mot_de_passe_hash, role, assure_id, "
                    "prestataire_id) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (email) DO NOTHING",
                    (
                        email,
                        pwd_hash,
                        role,
                        assure_id if role == "assure" else None,
                        prestataire_id if role == "professionnel_sante" else None,
                    ),
                )
        logger.info("demo_users_ready")
    except psycopg.errors.UndefinedTable:
        logger.error("tables manquantes : appliquer les migrations (assures, utilisateurs...)")
    except Exception:  # noqa: BLE001
        logger.exception("demo_users_failed")
