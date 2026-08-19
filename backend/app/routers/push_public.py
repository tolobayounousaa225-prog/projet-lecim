"""Abonnement / désabonnement Web Push depuis la vitrine — anonyme, aucun compte
requis. Sert uniquement à alerter des actualités urgentes publiées par le BEN."""

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..database import get_db

router = APIRouter(prefix="/api/push", tags=["push"])

# Domaines connus des services de push des navigateurs — tout le reste est
# refusé. Sans cette liste, le serveur accepterait n'importe quelle URL et
# ferait ensuite une requête sortante vers elle (SSRF) à chaque actualité
# urgente publiée, puisque webpush() envoie réellement une requête HTTP à
# `endpoint` depuis le serveur.
ALLOWED_PUSH_ENDPOINT_SUFFIXES = (
    ".googleapis.com",
    ".push.services.mozilla.com",
    ".notify.windows.com",
    ".push.apple.com",
)


def _is_allowed_push_endpoint(endpoint: str) -> bool:
    try:
        parsed = urlparse(endpoint)
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    return any(host == suffix.lstrip(".") or host.endswith(suffix) for suffix in ALLOWED_PUSH_ENDPOINT_SUFFIXES)


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscribeIn(BaseModel):
    endpoint: str
    keys: PushKeys
    lang: str = "fr"


@router.get("/public-key")
def push_public_key():
    return {"publicKey": settings.vapid_public_key}


@router.post("/subscribe", status_code=201)
def push_subscribe(payload: PushSubscribeIn, db: Session = Depends(get_db)):
    if not _is_allowed_push_endpoint(payload.endpoint):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Endpoint de notification non reconnu")
    existing = db.query(models.PushSubscription).filter(models.PushSubscription.endpoint == payload.endpoint).first()
    if existing:
        existing.p256dh = payload.keys.p256dh
        existing.auth = payload.keys.auth
        existing.lang = payload.lang if payload.lang in {"fr", "ar"} else "fr"
    else:
        db.add(
            models.PushSubscription(
                endpoint=payload.endpoint,
                p256dh=payload.keys.p256dh,
                auth=payload.keys.auth,
                lang=payload.lang if payload.lang in {"fr", "ar"} else "fr",
            )
        )
    db.commit()
    return {"ok": True}


class PushUnsubscribeIn(BaseModel):
    endpoint: str


@router.post("/unsubscribe")
def push_unsubscribe(payload: PushUnsubscribeIn, db: Session = Depends(get_db)):
    db.query(models.PushSubscription).filter(models.PushSubscription.endpoint == payload.endpoint).delete()
    db.commit()
    return {"ok": True}
