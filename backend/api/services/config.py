"""Read and update the existing key/value application configuration."""
from api import repositories as repo
from api.audit import write_audit
from api.config import get_settings
from api.schemas_admin import AdminSettings

_CONFIG_KEYS = (
    "seuil_alerte",
    "condition_etendue",
    "notif_slack",
    "notif_slack_canal",
    "notif_email",
    "notif_email_destinataire",
)


def get_admin_settings(conn) -> AdminSettings:
    rows = repo.get_config_values(conn, list(_CONFIG_KEYS))
    settings = get_settings()
    threshold = float(rows["seuil_alerte"]["valeur"]) if "seuil_alerte" in rows else (
        settings.alert_threshold
    )
    return AdminSettings(
        alert_threshold=threshold,
        extended_rule_enabled=(
            rows.get("condition_etendue", {}).get("valeur", "false").lower() == "true"
        ),
        channels={
            "slack": {
                "enabled": rows.get("notif_slack", {}).get("valeur", "true").lower() == "true",
                "channel": rows.get("notif_slack_canal", {}).get(
                    "valeur", "#alertes-fraude"
                ),
            },
            "email": {
                "enabled": rows.get("notif_email", {}).get("valeur", "false").lower() == "true",
                "address": rows.get("notif_email_destinataire", {}).get(
                    "valeur", settings.admin_email
                ),
            },
        },
    )


def update_admin_settings(conn, user: dict, settings: AdminSettings) -> AdminSettings:
    current = get_admin_settings(conn).model_dump()
    updated = settings.model_dump()
    updated_values = {
        "seuil_alerte": repr(updated["alert_threshold"]),
        "condition_etendue": str(updated["extended_rule_enabled"]).lower(),
        "notif_slack": str(updated["channels"]["slack"]["enabled"]).lower(),
        "notif_slack_canal": updated["channels"]["slack"]["channel"],
        "notif_email": str(updated["channels"]["email"]["enabled"]).lower(),
        "notif_email_destinataire": updated["channels"]["email"]["address"],
    }
    old_values = {
        "seuil_alerte": repr(current["alert_threshold"]),
        "condition_etendue": str(current["extended_rule_enabled"]).lower(),
        "notif_slack": str(current["channels"]["slack"]["enabled"]).lower(),
        "notif_slack_canal": current["channels"]["slack"]["channel"],
        "notif_email": str(current["channels"]["email"]["enabled"]).lower(),
        "notif_email_destinataire": current["channels"]["email"]["address"],
    }
    changes = {
        key: {"ancien": old_values[key], "nouveau": value}
        for key, value in updated_values.items()
        if old_values[key] != value
    }
    if changes:
        for key, change in changes.items():
            repo.set_config(conn, key, change["nouveau"], user["email"])
        write_audit(
            conn,
            event_type="configuration_modifiee",
            actor_id=user["user_id"],
            entity_type="configuration",
            entity_id="admin",
            input_data={"modifications": changes},
            output_data={"cles_modifiees": sorted(changes)},
        )
    return settings
