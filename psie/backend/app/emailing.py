import logging
import smtplib
from email.message import EmailMessage

from .config import settings

logger = logging.getLogger("psie.email")


def email_configured() -> bool:
    return bool(settings.smtp_host)


def send_email(to: str, subject: str, body: str) -> bool:
    """Envoie un e-mail texte. Retourne True si le serveur SMTP l'a accepté, False sinon
    (SMTP non configuré ou erreur) : l'appelant décide quoi faire d'un échec."""
    if not email_configured():
        logger.warning("SMTP non configuré : e-mail non envoyé (%s)", subject)
        return False
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
        return True
    except (OSError, smtplib.SMTPException):
        logger.exception("Échec d'envoi d'e-mail (%s)", subject)
        return False
