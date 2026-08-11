"""Suivi des mandats électifs du BEN : alerte l'administrateur et le président
quand un mandat approche de son échéance (60 jours)."""

import datetime

from . import models
from .database import SessionLocal
from .notifications import notify

ALERT_WINDOW_DAYS = 60


def check_mandate_expirations() -> int:
    """Notifie une fois chaque mandat qui entre dans la fenêtre d'alerte.
    Retourne le nombre de membres notifiés."""
    db = SessionLocal()
    total = 0
    try:
        seuil = datetime.date.today() + datetime.timedelta(days=ALERT_WINDOW_DAYS)
        membres = (
            db.query(models.Membre)
            .filter(
                models.Membre.mandat_fin.isnot(None),
                models.Membre.mandat_fin <= seuil,
                models.Membre.mandat_alert_sent.is_(False),
                models.Membre.delegation_id.is_(None),
            )
            .all()
        )
        if not membres:
            return 0

        destinataires = [u for u in db.query(models.User).all() if u.is_admin or u.poste == "president"]
        for membre in membres:
            message = (
                f"Le mandat de {membre.full_name} ({membre.poste_label}) arrive à échéance "
                f"le {membre.mandat_fin.strftime('%d/%m/%Y')}."
            )
            for user in destinataires:
                notify(db, user.id, message, link="/admin/membres")
            membre.mandat_alert_sent = True
            total += 1
        db.commit()
    finally:
        db.close()
    return total
