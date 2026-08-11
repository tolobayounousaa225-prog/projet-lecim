"""Envoi d'e-mails sortants (relances, notifications) via le SMTP configuré."""

import smtplib
from email.message import EmailMessage

from .config import settings


def send_email(to: str, subject: str, body: str) -> bool:
    if not settings.smtp_host or not to:
        return False
    try:
        email = EmailMessage()
        email["Subject"] = subject
        email["From"] = settings.smtp_from
        email["To"] = to
        email.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(email)
        return True
    except Exception:
        return False
