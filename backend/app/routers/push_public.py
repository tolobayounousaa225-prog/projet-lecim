"""Abonnement / désabonnement Web Push depuis la vitrine — anonyme, aucun compte
requis. Sert uniquement à alerter des actualités urgentes publiées par le BEN."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..database import get_db

router = APIRouter(prefix="/api/push", tags=["push"])


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
