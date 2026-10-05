"""Suivi des réponses au courrier arrivé : notifie et e-maile une fois les comptes
ayant accès au registre dès qu'un courrier reste « en attente de réponse » au-delà du
délai choisi lors de sa saisie."""

import datetime

from . import models
from .database import SessionLocal
from .email_utils import send_email
from .notifications import notify


def check_overdue_courrier() -> int:
    """Notifie une fois chaque courrier arrivé dont le délai de relance est dépassé
    sans réponse. Retourne le nombre de courriers signalés."""
    db = SessionLocal()
    total = 0
    try:
        today = datetime.date.today()
        courriers = (
            db.query(models.Courrier)
            .filter(
                models.Courrier.type == "arrivee",
                models.Courrier.statut_reponse == "en_attente",
                models.Courrier.relance_envoyee.is_(False),
            )
            .all()
        )
        if not courriers:
            return 0

        destinataires = [u for u in db.query(models.User).all() if u.has_module("courrier")]
        for courrier in courriers:
            echeance = courrier.date_courrier + datetime.timedelta(days=courrier.delai_relance_jours)
            if echeance >= today:
                continue
            message = (
                f"Courrier « {courrier.numero} » ({courrier.correspondant}) toujours sans réponse "
                f"depuis le {courrier.date_courrier.strftime('%d/%m/%Y')}."
            )
            for user in destinataires:
                notify(db, user.id, message, link="/admin/courrier")
                if user.email:
                    send_email(
                        user.email,
                        "[LECIM] Courrier sans réponse",
                        f"Bonjour {user.full_name},\n\n{message}\n\n"
                        "Consultez le registre du courrier pour y répondre ou mettre à jour son statut.\n\n"
                        "LECIM — Ligue des Établissements Confessionnels et Madrassas de Côte d'Ivoire",
                    )
            courrier.relance_envoyee = True
            total += 1
        db.commit()
    finally:
        db.close()
    return total
