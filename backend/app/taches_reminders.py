"""Suivi des tâches personnelles : notifie et e-maile une fois le propriétaire d'une
tâche dès que son échéance est dépassée sans être marquée terminée."""

import datetime

from . import models
from .database import SessionLocal
from .email_utils import send_email
from .notifications import notify


def check_overdue_taches() -> int:
    """Notifie une fois chaque tâche en retard qui n'a pas encore été signalée.
    Retourne le nombre de tâches notifiées."""
    db = SessionLocal()
    total = 0
    try:
        today = datetime.date.today()
        taches = (
            db.query(models.TachePersonnelle)
            .filter(
                models.TachePersonnelle.echeance.isnot(None),
                models.TachePersonnelle.echeance < today,
                models.TachePersonnelle.is_done.is_(False),
                models.TachePersonnelle.retard_rappel_envoye.is_(False),
            )
            .all()
        )
        for tache in taches:
            user = db.get(models.User, tache.user_id)
            if not user:
                continue
            message = f"Tâche en retard : « {tache.titre} » (échéance dépassée le {tache.echeance.strftime('%d/%m/%Y')})."
            notify(db, user.id, message, link="/admin/taches")
            if user.email:
                send_email(
                    user.email,
                    "[LECIM] Tâche en retard",
                    f"Bonjour {user.full_name},\n\n{message}\n\n"
                    "Connectez-vous à votre espace LECIM (rubrique « Mes tâches ») pour la mettre à jour.\n\n"
                    "LECIM — Ligue des Établissements Confessionnels et Madrassas de Côte d'Ivoire",
                )
            tache.retard_rappel_envoye = True
            total += 1
        db.commit()
    finally:
        db.close()
    return total
