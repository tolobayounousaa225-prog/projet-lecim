"""Inscription / désinscription libre-service à la newsletter mensuelle de la
LECIM — anonyme, aucun compte requis. Le résumé mensuel est envoyé par
scheduler.py (voir newsletter.py)."""

import secrets

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/api/newsletter", tags=["newsletter"])


class NewsletterSubscribeIn(BaseModel):
    email: EmailStr


@router.post("/subscribe", status_code=201)
def newsletter_subscribe(payload: NewsletterSubscribeIn, db: Session = Depends(get_db)):
    existing = db.query(models.NewsletterSubscriber).filter(models.NewsletterSubscriber.email == payload.email).first()
    if existing:
        existing.is_active = True
    else:
        db.add(
            models.NewsletterSubscriber(
                email=payload.email,
                unsubscribe_token=secrets.token_urlsafe(24),
            )
        )
    db.commit()
    return {"ok": True}


@router.get("/unsubscribe", response_class=HTMLResponse)
def newsletter_unsubscribe(token: str, db: Session = Depends(get_db)):
    subscriber = db.query(models.NewsletterSubscriber).filter(models.NewsletterSubscriber.unsubscribe_token == token).first()
    if subscriber:
        subscriber.is_active = False
        db.commit()
        message = "Vous avez été désinscrit(e) de la newsletter de la LECIM."
    else:
        message = "Ce lien de désinscription n'est plus valide."
    return HTMLResponse(
        f"<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        f"<title>Désinscription — LECIM</title></head>"
        f"<body style='font-family:sans-serif; text-align:center; padding:60px 20px;'>"
        f"<h1 style='color:#0b3d2e;'>LECIM</h1><p>{message}</p>"
        f"<p><a href='/index.html'>Retour à l'accueil</a></p></body></html>"
    )
