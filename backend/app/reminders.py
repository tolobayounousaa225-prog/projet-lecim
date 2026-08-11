"""Rappels automatiques par e-mail avant les réunions du BEN et des délégations.
Tâche planifiée quotidienne (voir scheduler.py) + déclenchement manuel possible
depuis la fiche d'une réunion."""

import datetime

from sqlalchemy.orm import Session

from . import models
from .database import SessionLocal
from .email_utils import send_email
from .notifications import notify

REMINDER_DAYS_BEFORE = 3


def send_reminder_for_reunion(db: Session, reunion: models.Reunion) -> int:
    """Envoie le rappel (e-mail + notification interne) pour une réunion donnée.
    Retourne le nombre d'e-mails effectivement envoyés."""
    membres = (
        db.query(models.Membre)
        .filter(models.Membre.delegation_id == reunion.delegation_id, models.Membre.email.isnot(None))
        .all()
    )
    subject = f"[LECIM] Rappel — {reunion.title}"
    body = (
        f"Rappel : la réunion « {reunion.title} » aura lieu le "
        f"{reunion.date.strftime('%d/%m/%Y')}"
        + (f", à {reunion.lieu}" if reunion.lieu else "")
        + ".\n\n"
        + (f"Ordre du jour :\n{reunion.ordre_du_jour}\n\n" if reunion.ordre_du_jour else "")
        + "LECIM — Ligue des Établissements Confessionnels et Madrassas de Côte d'Ivoire"
    )

    envoyes = 0
    for membre in membres:
        if send_email(membre.email, subject, body):
            envoyes += 1

    users_query = db.query(models.User)
    if reunion.delegation_id:
        users = users_query.filter(models.User.delegation_id == reunion.delegation_id).all()
    else:
        users = [u for u in users_query.all() if u.can_manage_reunions and not u.is_delegation_account]

    for user in users:
        notify(
            db,
            user.id,
            f"Rappel : la réunion « {reunion.title} » aura lieu le {reunion.date.strftime('%d/%m/%Y')}.",
            link="/delegation/reunions" if reunion.delegation_id else "/admin/calendrier",
        )
        if user.email and send_email(user.email, subject, body):
            envoyes += 1

    reunion.reminder_sent = True
    db.commit()
    return envoyes


def run_daily_reminders() -> int:
    """Appelée par le scheduler : envoie les rappels pour toutes les réunions
    prévues dans REMINDER_DAYS_BEFORE jours et pas encore rappelées."""
    target_date = datetime.date.today() + datetime.timedelta(days=REMINDER_DAYS_BEFORE)
    db = SessionLocal()
    total = 0
    try:
        reunions = (
            db.query(models.Reunion)
            .filter(models.Reunion.date == target_date, models.Reunion.reminder_sent.is_(False))
            .all()
        )
        for reunion in reunions:
            total += send_reminder_for_reunion(db, reunion)
    finally:
        db.close()
    return total
