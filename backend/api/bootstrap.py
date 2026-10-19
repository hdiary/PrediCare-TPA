"""Création des comptes de démonstration au démarrage (idempotent)."""
import logging

from api.config import get_settings
from api.db import get_pool
from api.security import hash_password

logger = logging.getLogger(__name__)

DEMO_USERS = [
    ("pro@predicare.local", "professionnel_sante"),
    ("assure@predicare.local", "assure"),
    ("gestionnaire@predicare.local", "gestionnaire"),
]


def _pick(conn, query: str) -> str | None:
    row = conn.execute(query).fetchone()
    return next(iter(row.values())) if row else None


def ensure_demo_users() -> None:
    """Create the initial administrator and optional demonstration accounts.

    The insured user is linked to a principal insured person with invoices; the
    professional user is linked to an active provider with invoices. Existing
    accounts are never reset or overwritten.
    """
    settings = get_settings()
    pool = get_pool()
    if pool is None:
        logger.warning("initial_users_skipped", extra={"reason": "database_pool_unavailable"})
        return

    admin_password = getattr(settings, "admin_initial_password", None)
    demo_password = settings.demo_password
    admin_email = getattr(settings, "admin_email", "admin@predicare.local").strip().lower()
    if admin_password and not admin_email:
        raise ValueError("ADMIN_EMAIL must not be empty when ADMIN_INITIAL_PASSWORD is set")
    if not admin_password and not demo_password:
        logger.warning(
            "initial_users_skipped",
            extra={"reason": "ADMIN_INITIAL_PASSWORD and DEMO_PASSWORD are not configured"},
        )
        return

    with pool.connection(timeout=10) as conn:
        if admin_password:
            inserted = conn.execute(
                "INSERT INTO utilisateurs (email, mot_de_passe_hash, role) "
                "VALUES (%s, %s, 'administrateur') ON CONFLICT (email) DO NOTHING "
                "RETURNING utilisateur_id",
                (admin_email, hash_password(admin_password)),
            ).fetchone()
            if inserted is None:
                existing = conn.execute(
                    "SELECT role FROM utilisateurs WHERE email = %s",
                    (admin_email,),
                ).fetchone()
                if not existing or existing["role"] != "administrateur":
                    raise RuntimeError(
                        "ADMIN_EMAIL already belongs to a non-administrator account"
                    )
            logger.info("initial_admin_ready")
        else:
            logger.warning(
                "initial_admin_skipped",
                extra={"reason": "ADMIN_INITIAL_PASSWORD is not configured"},
            )

        if demo_password:
            demo_hash = hash_password(demo_password)
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
            if assure_id is None or prestataire_id is None:
                raise RuntimeError(
                    "Demo users require an existing insured person and active provider with invoices"
                )
            for email, role in DEMO_USERS:
                conn.execute(
                    "INSERT INTO utilisateurs (email, mot_de_passe_hash, role, assure_id, "
                    "prestataire_id) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (email) DO NOTHING",
                    (
                        email,
                        demo_hash,
                        role,
                        assure_id if role == "assure" else None,
                        prestataire_id if role == "professionnel_sante" else None,
                    ),
                )
            logger.info("demo_users_ready")
        else:
            logger.info("demo_users_skipped")
