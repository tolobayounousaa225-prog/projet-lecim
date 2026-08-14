"""Envoi de notifications Web Push aux visiteurs abonnés (actualités urgentes).
No-op silencieux si les clés VAPID ne sont pas configurées — la fonctionnalité
est alors simplement désactivée, sans erreur."""

import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from . import models
from .config import settings

logger = logging.getLogger(__name__)

TITLES_BY_LANG = {
    "fr": "LECIM — Actualité urgente",
    "ar": "LECIM — خبر عاجل",
}


def send_urgent_news_push(db: Session, news: models.NewsPost) -> None:
    if not settings.vapid_private_key or not settings.vapid_public_key:
        return

    subscriptions = db.query(models.PushSubscription).all()
    if not subscriptions:
        return

    url = f"{settings.public_base_url}/actualite.html?id={news.id}"
    vapid_claims = {"sub": f"mailto:{settings.vapid_claim_email}"}

    stale_ids: list[int] = []
    for sub in subscriptions:
        payload = json.dumps(
            {
                "title": TITLES_BY_LANG.get(sub.lang, TITLES_BY_LANG["fr"]),
                "body": news.title,
                "url": url,
            }
        )
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims=dict(vapid_claims),
            )
        except WebPushException as exc:
            status_code = getattr(exc.response, "status_code", None)
            if status_code in (404, 410):
                stale_ids.append(sub.id)
            else:
                logger.warning("Échec d'envoi push (endpoint %s) : %s", sub.endpoint[:60], exc)

    if stale_ids:
        db.query(models.PushSubscription).filter(models.PushSubscription.id.in_(stale_ids)).delete(
            synchronize_session=False
        )
        db.commit()
