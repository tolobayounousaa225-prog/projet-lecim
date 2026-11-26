"""Notifications : cloche dans l'application + e-mail (si la personne l'accepte) + canaux supplémentaires branchables.

Un évènement de la vie de la plateforme (nouvelle demande, convention à examiner, bilan à valider, réponse à une demande…)
appelle `notify_*`. L'enregistrement est dans la même transaction que l'évènement ; l'e-mail est envoyé au mieux
(un échec d'envoi ne bloque jamais l'action de l'utilisateur).

SMS / WhatsApp : écrire une fonction `canal(user, titre, texte, lien)` et l'enregistrer avec `register_channel`
(voir docs/EXPLOITATION.md). Aucun fournisseur n'est branché par défaut."""

import logging
from typing import Callable, Iterable

from sqlalchemy.orm import Session

from . import models
from .config import settings
from .emailing import send_email

logger = logging.getLogger("psie.notifier")
Channel = Callable[["models.User", str, str, str], None]
CHANNELS: list[Channel] = []


def register_channel(channel: Channel) -> None:
    CHANNELS.append(channel)


def _absolute(link: str | None) -> str:
    return f"{settings.public_base_url.rstrip('/')}{link}" if link else settings.public_base_url.rstrip("/")


def notify(db: Session, users: Iterable["models.User"] | "models.User", titre: str, texte: str | None = None,
           lien: str | None = None, kind: str = "info", email: bool = True, sender=None, exclude_id: int | None = None) -> int:
    """Crée la notification de chaque destinataire actif (sauf `exclude_id`, l'auteur de l'action). Retourne leur nombre."""
    sender = sender or send_email
    if isinstance(users, models.User):
        users = [users]
    seen: set[int] = set()
    count = 0
    for u in users:
        if u is None or not u.is_active or u.id in seen or u.id == exclude_id:
            continue
        seen.add(u.id)
        db.add(models.Notification(user_id=u.id, kind=kind, titre=titre[:255], texte=texte, lien=lien))
        count += 1
        body = f"{titre}\n\n{texte + chr(10) + chr(10) if texte else ''}{_absolute(lien)}\n\n— Plateforme des Structures Islamiques d'Éducation (PSIE)"
        if email and u.notif_email:
            try:
                sender(u.email, f"PSIE — {titre}", body)
            except Exception:
                logger.exception("Notification e-mail non envoyée à %s", u.email)
        for channel in CHANNELS:
            try:
                channel(u, titre, texte or "", _absolute(lien))
            except Exception:
                logger.exception("Canal de notification en échec")
    return count


def notify_roles(db: Session, roles: Iterable[str], titre: str, **kw) -> int:
    roles = set(roles)
    users = db.query(models.User).filter(models.User.role.in_(roles), models.User.is_active.is_(True)).all()
    return notify(db, users, titre, **kw)


def notify_faitiere(db: Session, faitiere_id: int, titre: str, **kw) -> int:
    users = db.query(models.User).filter_by(faitiere_id=faitiere_id, role="faitiere", is_active=True).all()
    return notify(db, users, titre, **kw)


def notify_all_faitieres(db: Session, titre: str, **kw) -> int:
    users = db.query(models.User).filter_by(role="faitiere", is_active=True).all()
    return notify(db, users, titre, **kw)


def unread_count(db: Session, user_id: int) -> int:
    return db.query(models.Notification).filter_by(user_id=user_id, lue_at=None).count()
