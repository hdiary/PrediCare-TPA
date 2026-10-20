"""E-mails transactionnels (SMTP) : jamais bloquants, aucune adresse dans les journaux.

Sans SMTP_HOST, rien n'est envoyé. En développement, DEV_LOG_RESET_LINK=true écrit le lien de
réinitialisation dans les journaux pour pouvoir tester sans serveur de messagerie.
"""
import logging
import re
import smtplib
import ssl
from email.message import EmailMessage
from typing import Iterable

from api import repositories as repo
from api.config import get_settings

logger = logging.getLogger(__name__)


def send_mail(to: str | Iterable[str], subject: str, body: str) -> bool:
    """Envoie un e-mail texte. Retourne False (sans lever) si SMTP absent ou en échec."""
    s = get_settings()
    if not s.smtp_host:
        return False
    msg = EmailMessage()
    msg["From"] = s.smtp_from
    recipients = [to] if isinstance(to, str) else list(to)
    if not recipients:
        return False
    msg["To"] = recipients[0] if len(recipients) == 1 else "undisclosed-recipients:;"
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        if s.smtp_port == 465:   # TLS implicite
            smtp = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=10,
                                    context=ssl.create_default_context())
        else:
            smtp = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10)
        with smtp:
            if s.smtp_port != 465 and s.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if s.smtp_user and s.smtp_password:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg, to_addrs=recipients)
        return True
    except Exception as exc:  # noqa: BLE001 - un SMTP en panne ne doit jamais faire échouer l'API
        logger.warning("mail_send_failed: %s", type(exc).__name__)
        return False


def smtp_is_configured() -> bool:
    settings = get_settings()
    return bool(settings.smtp_host and settings.smtp_from)


def configured_alert_recipients(conn) -> tuple[bool, list[str]]:
    rows = repo.get_config_values(conn, ["notif_email", "notif_email_destinataire"])
    enabled = rows.get("notif_email", {}).get("valeur", "false").lower() == "true"
    address = rows.get("notif_email_destinataire", {}).get("valeur", "")
    recipients = [value.strip() for value in re.split(r"[,;]", address) if value.strip()]
    return enabled, recipients


def send_alert_email(conn, alert: dict) -> bool:
    """Send a minimal fraud-alert message to the administrators' configured recipients."""
    enabled, recipients = configured_alert_recipients(conn)
    if not enabled or not recipients:
        return False
    subject = f"PrediCare TPA - Alerte facture {alert.get('facture_id', '')}"
    codes = ", ".join(alert.get("codes_fraude") or []) or "Aucun code détaillé"
    body = (
        "Une facture nécessite une vérification dans l'espace gestionnaire PrediCare TPA.\n\n"
        f"Facture : {alert.get('facture_id', '—')}\n"
        f"Score : {alert.get('score', '—')} (seuil : {alert.get('seuil', '—')})\n"
        f"Montant : {alert.get('montant_total', '—')} MGA\n"
        f"Codes : {codes}\n\n"
        "Aucune identité d'assuré n'est incluse dans cet e-mail."
    )
    return send_mail(recipients, subject, body)


def send_reset_email(user_id: int, to: str, token: str) -> bool:
    """Envoie le lien de réinitialisation (le jeton n'est jamais journalisé hors mode dev)."""
    s = get_settings()
    lien = f"{s.app_public_url.rstrip('/')}{s.password_reset_path}?token={token}"
    if not s.smtp_host:
        if s.dev_log_reset_link:
            logger.warning("DEV reset_link user_id=%s lien=%s", user_id, lien)
        else:
            logger.warning("password_reset_mail_skipped: SMTP_HOST non défini",
                           extra={"user_id": user_id})
        return False
    corps = (
        "Bonjour,\n\n"
        "Une réinitialisation du mot de passe de votre compte PrediCare TPA a été demandée.\n"
        f"Ouvrez ce lien (valable {s.password_reset_ttl_minutes} minutes, usage unique) :\n\n"
        f"{lien}\n\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message : "
        "votre mot de passe reste inchangé.\n"
    )
    ok = send_mail(to, "PrediCare TPA - Réinitialisation de votre mot de passe", corps)
    logger.info("password_reset_mail", extra={"user_id": user_id, "sent": ok})
    return ok


def send_account_credentials(to: str, identifier: str, password: str) -> bool:
    """Envoie les identifiants initiaux sans jamais les écrire dans les journaux."""
    body = (
        "Bonjour,\n\n"
        "Votre compte PrediCare TPA a été créé par un administrateur.\n\n"
        f"Identifiant : {identifier}\n"
        f"Mot de passe provisoire : {password}\n\n"
        "Connectez-vous avec votre identifiant ou votre adresse e-mail. "
        "Pour votre sécurité, modifiez ce mot de passe après votre première connexion.\n"
    )
    sent = send_mail(to, "PrediCare TPA - Vos identifiants de connexion", body)
    logger.info("account_credentials_mail", extra={"sent": sent})
    return sent
