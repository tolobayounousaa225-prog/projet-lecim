"""Newsletter mensuelle : résumé des actualités publiées le mois précédent,
envoyé aux abonnés actifs. Tâche planifiée mensuelle (voir scheduler.py)."""

import datetime

from . import models
from .config import settings
from .database import SessionLocal
from .email_utils import send_email


def _digest_body(posts: list[models.NewsPost], unsubscribe_url: str) -> str:
    lines = ["Voici le résumé des actualités publiées ce mois-ci par la LECIM :", ""]
    for post in posts:
        lines.append(f"- {post.title} ({post.published_at.strftime('%d/%m/%Y')})")
        lines.append(f"  {settings.vitrine_base_url}/actualite.html?id={post.id}")
        lines.append("")
    lines.append("LECIM — Ligue des Établissements Confessionnels et Madrassas de Côte d'Ivoire")
    lines.append("")
    lines.append(f"Pour ne plus recevoir cette newsletter : {unsubscribe_url}")
    return "\n".join(lines)


def run_monthly_newsletter() -> int:
    """Appelée par le scheduler le 1er de chaque mois : envoie le résumé des
    actualités du mois précédent à tous les abonnés actifs. Retourne le nombre
    d'e-mails effectivement envoyés."""
    today = datetime.date.today()
    premier_du_mois = today.replace(day=1)
    mois_precedent_fin = premier_du_mois - datetime.timedelta(days=1)
    mois_precedent_debut = mois_precedent_fin.replace(day=1)

    db = SessionLocal()
    envoyes = 0
    try:
        posts = (
            db.query(models.NewsPost)
            .filter(
                models.NewsPost.is_published.is_(True),
                models.NewsPost.published_at >= mois_precedent_debut,
                models.NewsPost.published_at <= mois_precedent_fin,
            )
            .order_by(models.NewsPost.published_at)
            .all()
        )
        if not posts:
            return 0

        subscribers = (
            db.query(models.NewsletterSubscriber)
            .filter(models.NewsletterSubscriber.is_active.is_(True))
            .all()
        )
        subject = f"[LECIM] Actualités de {mois_precedent_debut.strftime('%B %Y')}"
        for subscriber in subscribers:
            unsubscribe_url = f"{settings.public_base_url}/api/newsletter/unsubscribe?token={subscriber.unsubscribe_token}"
            body = _digest_body(posts, unsubscribe_url)
            if send_email(subscriber.email, subject, body):
                envoyes += 1
    finally:
        db.close()
    return envoyes
