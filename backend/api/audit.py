"""Journal d'audit (AI Act art. 12).

Une ligne par prédiction, décision, rejet ou accès sensible.
"""
from psycopg.types.json import Jsonb


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
