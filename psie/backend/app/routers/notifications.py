"""Cloche et page « Notifications » : chacun ne voit, ne lit et ne règle que les siennes."""

import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..web import render

router = APIRouter()


@router.get("/notifications")
def notifications_page(request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(models.Notification).filter_by(user_id=user.id).order_by(models.Notification.id.desc()).limit(100).all()
    return render(request, "notifications.html", user, items=items)


@router.get("/notifications/{notif_id}/ouvrir")
def notification_open(notif_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(models.Notification, notif_id)
    if not n or n.user_id != user.id:                       # jamais la notification d'une autre personne
        raise HTTPException(status_code=404, detail="Notification introuvable")
    if n.lue_at is None and user.supervisor is None:        # en consultation, on ne touche à rien
        n.lue_at = datetime.datetime.utcnow()
        db.commit()
    link = n.lien if (n.lien or "").startswith("/") and not (n.lien or "").startswith("//") else "/notifications"
    return RedirectResponse(link, status_code=303)


@router.post("/notifications/tout-lire")
def notifications_read_all(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(models.Notification).filter_by(user_id=user.id, lue_at=None).update({"lue_at": datetime.datetime.utcnow()})
    db.commit()
    return RedirectResponse("/notifications", status_code=303)


@router.post("/notifications/preferences")
def notifications_preferences(email: str = Form(""), user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.get(models.User, user.id).notif_email = bool(email)
    db.commit()
    return RedirectResponse("/notifications", status_code=303)
