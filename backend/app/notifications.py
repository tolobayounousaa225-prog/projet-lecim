"""Notifications affichées dans l'espace personnel de chaque compte."""

from sqlalchemy.orm import Session

from . import models


def notify(db: Session, user_id: int, message: str, link: str | None = None) -> None:
    db.add(models.Notification(user_id=user_id, message=message, link=link))


def notify_cartes_gestionnaires(db: Session, message: str, link: str | None = None) -> None:
    """Notifie tous les comptes habilités à gérer les cartes de membres (+ les administrateurs)."""
    users = db.query(models.User).all()
    for user in users:
        if user.is_admin or user.can_manage_cartes:
            notify(db, user.id, message, link)


def notify_cartes_scolaires_gestionnaires(db: Session, message: str, link: str | None = None) -> None:
    """Notifie tous les comptes habilités à gérer les cartes scolaires (+ les administrateurs)."""
    users = db.query(models.User).all()
    for user in users:
        if user.is_admin or user.can_manage_cartes_scolaires:
            notify(db, user.id, message, link)


def notify_messagerie_gestionnaires(db: Session, message: str, link: str | None = None) -> None:
    """Notifie tous les comptes habilités à gérer la messagerie établissements (+ les administrateurs)."""
    users = db.query(models.User).all()
    for user in users:
        if user.is_admin or user.can_manage_messagerie:
            notify(db, user.id, message, link)
