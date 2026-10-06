"""Rappels automatiques par e-mail avant les réunions du BEN et des délégations.
Tâche planifiée quotidienne (voir scheduler.py) + déclenchement manuel possible
depuis la fiche d'une réunion."""

import datetime

from sqlalchemy.orm import Session

from . import models
from .config import settings
from .database import SessionLocal
from .email_utils import send_email
from .notifications import notify

REMINDER_DAYS_BEFORE = 3
# Fenêtre avant l'heure de début d'une réunion pendant laquelle le rappel programmé de
# visioconférence est envoyé (le job tourne toutes les 10 min, voir scheduler.py).
VISIO_REMINDER_WINDOW_MINUTES = 15


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


def send_visio_invitation(db: Session, reunion: models.Reunion, started_by: models.User) -> int:
    """Déclenchée explicitement (bouton dédié, distinct de l'ouverture de l'appel)
    quand un appel vidéo vient de démarrer pour une réunion — notifie et e-maile tous
    les membres concernés avec un lien direct pour rejoindre immédiatement. Même
    logique de destinataires que send_reminder_for_reunion (roster `Membre` + comptes
    `User`), mais sans marquer `reminder_sent` : ce n'est pas un rappel planifié, donc
    rien n'empêche de relancer une invitation plusieurs fois pour la même réunion."""
    link = f"{settings.public_base_url}/admin/reunions/{reunion.id}/visio"
    subject = f"[LECIM] Appel en cours — {reunion.title}"
    body = (
        f"{started_by.full_name} vient de démarrer l'appel vidéo pour la réunion "
        f"« {reunion.title} ».\n\n"
        f"Rejoignez maintenant : {link}\n\n"
        "(Connectez-vous à votre espace LECIM si ce n'est pas déjà fait, puis cliquez "
        "à nouveau sur ce lien.)\n\n"
        "LECIM — Ligue des Établissements Confessionnels et Madrassas de Côte d'Ivoire"
    )

    membres = (
        db.query(models.Membre)
        .filter(models.Membre.delegation_id == reunion.delegation_id, models.Membre.email.isnot(None))
        .all()
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
        if user.id == started_by.id:
            continue
        notify(
            db,
            user.id,
            f"{started_by.full_name} a démarré l'appel vidéo de la réunion « {reunion.title} ». Rejoignez maintenant.",
            link=f"/admin/reunions/{reunion.id}/visio",
        )
        if user.email and send_email(user.email, subject, body):
            envoyes += 1

    db.commit()
    return envoyes


def send_visio_reminder_for_reunion(db: Session, reunion: models.Reunion) -> int:
    """Rappel automatique programmé, envoyé peu avant l'heure de début d'une réunion
    nationale, avec le lien direct pour rejoindre la visioconférence. Distinct de
    send_visio_invitation (déclenché manuellement quand un appel démarre réellement) :
    celui-ci se base uniquement sur `Reunion.heure` et ne s'envoie qu'une fois par
    réunion (voir `visio_reminder_sent`). Réunions de délégation exclues : la
    visioconférence n'existe aujourd'hui que côté BEN national."""
    link = f"{settings.public_base_url}/admin/reunions/{reunion.id}/visio"
    heure_str = reunion.heure.strftime("%Hh%M") if reunion.heure else ""
    subject = f"[LECIM] La réunion « {reunion.title} » commence bientôt"
    body = (
        f"La réunion « {reunion.title} » commence dans quelques minutes"
        + (f" (prévue à {heure_str})" if heure_str else "")
        + ".\n\n"
        f"Rejoignez la visioconférence : {link}\n\n"
        "(Connectez-vous à votre espace LECIM si ce n'est pas déjà fait, puis cliquez "
        "à nouveau sur ce lien.)\n\n"
        "LECIM — Ligue des Établissements Confessionnels et Madrassas de Côte d'Ivoire"
    )

    membres = (
        db.query(models.Membre)
        .filter(models.Membre.delegation_id.is_(None), models.Membre.email.isnot(None))
        .all()
    )
    envoyes = 0
    for membre in membres:
        if send_email(membre.email, subject, body):
            envoyes += 1

    users = [u for u in db.query(models.User).all() if u.can_manage_reunions and not u.is_delegation_account]
    for user in users:
        notify(
            db,
            user.id,
            f"La réunion « {reunion.title} » commence bientôt. Rejoignez la visioconférence.",
            link=f"/admin/reunions/{reunion.id}/visio",
        )
        if user.email and send_email(user.email, subject, body):
            envoyes += 1

    reunion.visio_reminder_sent = True
    db.commit()
    return envoyes


def run_visio_reminders() -> int:
    """Appelée par le scheduler (toutes les 10 minutes) : envoie le rappel programmé de
    visioconférence aux réunions nationales du jour dont l'heure de début tombe dans la
    fenêtre VISIO_REMINDER_WINDOW_MINUTES et pas encore rappelées. Réunions sans heure
    renseignée : ignorées (impossible de calculer le moment d'envoi)."""
    now = datetime.datetime.now()
    db = SessionLocal()
    total = 0
    try:
        reunions = (
            db.query(models.Reunion)
            .filter(
                models.Reunion.delegation_id.is_(None),
                models.Reunion.date == now.date(),
                models.Reunion.heure.isnot(None),
                models.Reunion.visio_reminder_sent.is_(False),
            )
            .all()
        )
        for reunion in reunions:
            start = datetime.datetime.combine(reunion.date, reunion.heure)
            if start - datetime.timedelta(minutes=VISIO_REMINDER_WINDOW_MINUTES) <= now <= start + datetime.timedelta(minutes=30):
                total += send_visio_reminder_for_reunion(db, reunion)
            elif now > start + datetime.timedelta(minutes=30):
                # Réunion déjà bien avancée (ex. serveur indisponible au bon moment) : on
                # marque comme traité sans envoyer un rappel "commence bientôt" devenu faux.
                reunion.visio_reminder_sent = True
                db.commit()
    finally:
        db.close()
    return total


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
