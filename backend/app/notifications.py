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


def notify_adhesion_examinateurs(db: Session, message: str, link: str | None = None) -> None:
    """Notifie tous les comptes habilités à examiner les demandes d'adhésion (+ les administrateurs)."""
    users = db.query(models.User).all()
    for user in users:
        if user.is_admin or user.can_examine_adhesions:
            notify(db, user.id, message, link)


def notify_delegation_titulaire(db: Session, delegation_id: int, message: str, link: str | None = None) -> bool:
    """Notifie le titulaire actif de la délégation donnée, s'il existe. Retourne
    True si quelqu'un a effectivement été notifié (utile pour décider s'il faut
    basculer directement sur l'examen BEN faute de compte délégation actif)."""
    titulaire = (
        db.query(models.User)
        .filter(models.User.delegation_id == delegation_id, models.User.is_delegation_titulaire.is_(True))
        .first()
    )
    if not titulaire:
        return False
    notify(db, titulaire.id, message, link)
    return True
