"""Journal d'audit (AI Act art. 12).

Une ligne par prédiction, décision, rejet ou accès sensible.
"""
import logging

from psycopg.types.json import Jsonb

logger = logging.getLogger(__name__)


def write_audit(
    conn,
    *,
    event_type: str,
    actor_id: int | None,
    entity_type: str,
    entity_id: str | None,
    model_name: str | None = None,
    model_version: str | None = None,
    input_data: dict | None = None,
    output_data: dict | None = None,
) -> None:
    """Écrit dans la transaction de l'appelant : tout réussit ou tout est annulé."""
    conn.execute(
        "INSERT INTO journal_audit (type_evenement, utilisateur_id, type_entite, entite_id, "
        "nom_modele, version_modele, entree, sortie) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (
            event_type,
            actor_id,
            entity_type,
            entity_id,
            model_name,
            model_version,
            Jsonb(input_data) if input_data is not None else None,
            Jsonb(output_data) if output_data is not None else None,
        ),
    )


def write_audit_compte(conn, *, event_type: str, actor_id: int | None, entity_id: int | str,
                       input_data: dict | None = None, output_data: dict | None = None) -> None:
    """Audit des opérations sur les comptes (inscription, mot de passe, gestion par l'admin).

    Écrit dans un point de sauvegarde : si la table d'audit refuse ce type d'événement
    (contrainte CHECK propre à votre schéma), l'erreur est journalisée mais l'opération sur
    le compte n'est pas annulée. Ne jamais y mettre d'e-mail ni de mot de passe.
    """
    try:
        with conn.transaction():
            write_audit(conn, event_type=event_type, actor_id=actor_id, entity_type="utilisateur",
                        entity_id=str(entity_id), input_data=input_data, output_data=output_data)
    except Exception:  # noqa: BLE001
        logger.exception("audit_compte_failed", extra={"event_type": event_type})
