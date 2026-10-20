"""Provisionnement idempotent des comptes liés aux assurés et prestataires."""
import logging

from api.config import get_settings
from api.db import get_pool
from api.security import hash_password
from api.services.pseudonym import PseudonymConfigurationError, pseudonymise_account

logger = logging.getLogger(__name__)
DEFAULT_IDENTITY_PASSWORD = "123456"

DEMO_USERS = [
    ("pro@predicare.local", "professionnel_sante"),
    ("assure@predicare.local", "assure"),
    ("gestionnaire@predicare.local", "gestionnaire"),
]

SEED_USERS = [
    ("admin@predicare.com", "administrateur", "seed_admin_password"),
    ("gestion@predicare.com", "gestionnaire", "seed_gestion_password"),
    ("pds@predicare.com", "professionnel_sante", "seed_pds_password"),
]


def _ensure_user(
    conn,
    username: str,
    password_hash: str,
    role: str,
    *,
    assure_id: str | None = None,
    prestataire_id: str | None = None,
) -> int:
    row = conn.execute(
        "INSERT INTO utilisateurs "
        "(nom_utilisateur, hash_mot_de_passe, assure_id, prestataire_id) "
        "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING utilisateur_id",
        (username, password_hash, assure_id, prestataire_id),
    ).fetchone()
    if row is None:
        row = conn.execute(
            "SELECT utilisateur_id FROM utilisateurs "
            "WHERE lower(nom_utilisateur) = lower(%s)",
            (username,),
        ).fetchone()
    if row is None:
        raise RuntimeError(f"Impossible de créer le compte {username!r}")

    conn.execute(
        "INSERT INTO utilisateurs_roles (utilisateur_id, role_id) "
        "SELECT %s, role_id FROM roles WHERE nom_role = %s "
        "ON CONFLICT (utilisateur_id) DO NOTHING",
        (row["utilisateur_id"], role),
    )
    assigned = conn.execute(
        "SELECT r.nom_role FROM utilisateurs_roles ur "
        "JOIN roles r ON r.role_id = ur.role_id WHERE ur.utilisateur_id = %s",
        (row["utilisateur_id"],),
    ).fetchone()
    if not assigned or assigned["nom_role"] != role:
        raise RuntimeError(
            f"Le compte {username!r} possède déjà un rôle différent de {role!r}"
        )
    if assure_id is not None or prestataire_id is not None:
        conn.execute(
            "UPDATE utilisateurs SET assure_id = %s, prestataire_id = %s "
            "WHERE utilisateur_id = %s",
            (assure_id, prestataire_id, row["utilisateur_id"]),
        )
    return row["utilisateur_id"]


def ensure_identity_users() -> None:
    """Crée les comptes manquants sans remplacer les mots de passe déjà modifiés."""
    pool = get_pool()
    if pool is None:
        logger.warning("identity_users_skipped", extra={"reason": "database_pool_unavailable"})
        return

    with pool.connection(timeout=10) as conn:
        identities = conn.execute(
            "SELECT assure_id AS nom_utilisateur, 'assure' AS role FROM assures "
            "UNION ALL "
            "SELECT prestataire_id, 'professionnel_sante' FROM prestataires"
        ).fetchall()
        usernames = [identity["nom_utilisateur"] for identity in identities]
        roles = [identity["role"] for identity in identities]
        if not usernames:
            logger.info("identity_users_ready", extra={"count": 0})
            return

        collision = conn.execute(
            "SELECT nom_utilisateur FROM unnest(%s::text[], %s::text[]) "
            "AS expected(nom_utilisateur, role) "
            "GROUP BY nom_utilisateur HAVING count(DISTINCT role) > 1 LIMIT 1",
            (usernames, roles),
        ).fetchone()
        if collision:
            raise RuntimeError(
                f"Un identifiant est partagé par plusieurs types de compte: "
                f"{collision['nom_utilisateur']!r}"
            )

        wrong_role = conn.execute(
            "SELECT u.nom_utilisateur, r.nom_role FROM unnest(%s::text[], %s::text[]) "
            "AS expected(nom_utilisateur, role) "
            "JOIN utilisateurs u ON lower(u.nom_utilisateur) = lower(expected.nom_utilisateur) "
            "LEFT JOIN utilisateurs_roles ur ON ur.utilisateur_id = u.utilisateur_id "
            "LEFT JOIN roles r ON r.role_id = ur.role_id "
            "WHERE r.nom_role IS DISTINCT FROM expected.role LIMIT 1",
            (usernames, roles),
        ).fetchone()
        if wrong_role:
            raise RuntimeError(
                f"Le compte {wrong_role['nom_utilisateur']!r} a déjà le rôle "
                f"{wrong_role['nom_role']!r}, incompatible avec son identité"
            )

        password_hash = hash_password(DEFAULT_IDENTITY_PASSWORD)
        conn.execute(
            "INSERT INTO utilisateurs (nom_utilisateur, hash_mot_de_passe) "
            "SELECT DISTINCT nom_utilisateur, %s "
            "FROM unnest(%s::text[]) AS identities(nom_utilisateur) "
            "ON CONFLICT DO NOTHING",
            (password_hash, usernames),
        )
        conn.execute(
            "INSERT INTO utilisateurs_roles (utilisateur_id, role_id) "
            "SELECT u.utilisateur_id, r.role_id "
            "FROM unnest(%s::text[], %s::text[]) "
            "AS expected(nom_utilisateur, role) "
            "JOIN utilisateurs u ON lower(u.nom_utilisateur) = lower(expected.nom_utilisateur) "
            "JOIN roles r ON r.nom_role = expected.role "
            "ON CONFLICT (utilisateur_id) DO NOTHING",
            (usernames, roles),
        )
        conn.execute(
            "UPDATE utilisateurs u SET "
            "assure_id = CASE WHEN expected.role = 'assure' THEN expected.nom_utilisateur ELSE NULL END, "
            "prestataire_id = CASE WHEN expected.role = 'professionnel_sante' "
            "THEN expected.nom_utilisateur ELSE NULL END "
            "FROM unnest(%s::text[], %s::text[]) "
            "AS expected(nom_utilisateur, role) "
            "WHERE lower(u.nom_utilisateur) = lower(expected.nom_utilisateur)",
            (usernames, roles),
        )
        logger.info("identity_users_ready", extra={"count": len(usernames)})


def ensure_demo_users() -> None:
    """Create configured administrator/demo users and all entity-linked accounts."""
    ensure_identity_users()
    settings = get_settings()
    pool = get_pool()
    if pool is None:
        logger.warning("initial_users_skipped", extra={"reason": "database_pool_unavailable"})
        return

    admin_password = settings.admin_initial_password
    demo_password = settings.demo_password
    with pool.connection(timeout=10) as conn:
        if admin_password:
            admin_username = settings.admin_email.strip()
            _ensure_user(conn, admin_username, hash_password(admin_password), "administrateur")
        if demo_password:
            password_hash = hash_password(demo_password)
            assure_id = conn.execute(
                "SELECT assure_id FROM assures ORDER BY assure_id LIMIT 1"
            ).fetchone()
            prestataire_id = conn.execute(
                "SELECT prestataire_id FROM prestataires ORDER BY prestataire_id LIMIT 1"
            ).fetchone()
            for username, role in DEMO_USERS:
                _ensure_user(
                    conn,
                    username,
                    password_hash,
                    role,
                    assure_id=assure_id["assure_id"] if role == "assure" and assure_id else None,
                    prestataire_id=(
                        prestataire_id["prestataire_id"]
                        if role == "professionnel_sante" and prestataire_id else None
                    ),
                )
        logger.info("demo_users_ready")


def ensure_seed_users() -> None:
    """Create explicitly configured seed users without overwriting existing passwords."""
    settings = get_settings()
    wanted = [
        (username, role, getattr(settings, setting))
        for username, role, setting in SEED_USERS
        if getattr(settings, setting)
    ]
    pool = get_pool()
    if not wanted or pool is None:
        logger.info("seed_users_skipped")
        return

    with pool.connection(timeout=10) as conn:
        prestataire = conn.execute(
            "SELECT p.prestataire_id FROM prestataires p WHERE p.statut = 'ACTIF' "
            "AND EXISTS (SELECT 1 FROM factures f WHERE f.prestataire_id = p.prestataire_id) "
            "ORDER BY p.prestataire_id LIMIT 1"
        ).fetchone()
        for username, role, password in wanted:
            _ensure_user(
                conn,
                username,
                hash_password(password),
                role,
                prestataire_id=(
                    prestataire["prestataire_id"]
                    if role == "professionnel_sante" and prestataire else None
                ),
            )
    logger.info("seed_users_ready", extra={"count": len(wanted)})
