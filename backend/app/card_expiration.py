"""Suivi de l'échéance des cartes de membre : alerte le titulaire par e-mail et
notifie le BEN une fois chaque carte qui approche de sa date de validité."""

import datetime

from . import models
from .database import SessionLocal
from .email_utils import send_email
from .notifications import notify_cartes_gestionnaires

ALERT_WINDOW_DAYS = 90


def check_card_expirations() -> int:
    """Notifie une fois chaque carte de membre dont la validité entre dans la
    fenêtre d'alerte. Retourne le nombre de cartes notifiées."""
    db = SessionLocal()
    total = 0
    try:
        today = datetime.date.today()
        seuil = today + datetime.timedelta(days=ALERT_WINDOW_DAYS)
        cartes = (
            db.query(models.CarteMembre)
            .filter(
                models.CarteMembre.date_validite.isnot(None),
                models.CarteMembre.date_validite >= today,
                models.CarteMembre.date_validite <= seuil,
                models.CarteMembre.status.in_(["validee", "imprimee", "disponible"]),
                models.CarteMembre.expiration_alert_envoyee.is_(False),
            )
            .all()
        )
        if not cartes:
            return 0

        for carte in cartes:
            echeance = carte.date_validite.strftime("%d/%m/%Y")
            message = (
                f"La carte de membre de {carte.full_name_snapshot} "
                f"(N. {carte.numero_carte or '-'}) arrive à échéance le {echeance}."
            )
            notify_cartes_gestionnaires(db, message, link="/admin/cartes")

            titulaire = carte.user
            if titulaire and titulaire.email:
                send_email(
                    titulaire.email,
                    "[LECIM] Votre carte de membre arrive à échéance",
                    f"Bonjour {titulaire.full_name},\n\n"
                    f"Votre carte de membre LECIM (N. {carte.numero_carte or '-'}) arrive à échéance "
                    f"le {echeance}.\n\n"
                    "Merci de contacter le secrétariat de la LECIM pour son renouvellement.\n\n"
                    "LECIM — Ligue des Établissements Confessionnels et Madrassas de Côte d'Ivoire",
                )

            carte.expiration_alert_envoyee = True
            total += 1
        db.commit()
    finally:
        db.close()
    return total
