"""Pointage de présence par QR code — page ouverte au scan depuis le mode présentation
d'une réunion (vue projecteur). Aucune authentification requise : certains membres du
répertoire n'ont pas de compte de connexion (voir Membre), donc on ne peut pas s'appuyer
sur une session LECIM pour savoir qui scanne. Le membre confirme lui-même son identité en
touchant son nom dans la liste des membres attendus — même niveau de confiance qu'une
feuille de présence papier faisant circuler, pas une preuve cryptographique d'identité.

Le jeton (Reunion.checkin_token) est opaque et jamais l'id séquentiel de la réunion, et
le pointage n'est accepté que le jour même de la réunion, pour qu'un vieux QR code projeté
par le passé ne puisse pas servir à pointer une présence a posteriori."""

import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette import status

from .. import models
from ..database import get_db
from ..rate_limit import rate_limiter

router = APIRouter(prefix="/checkin", tags=["checkin"], dependencies=[Depends(rate_limiter("checkin", 30, 60))])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def _reunion_du_jour(db: Session, token: str) -> models.Reunion | None:
    reunion = db.query(models.Reunion).filter(models.Reunion.checkin_token == token).first()
    if not reunion or reunion.date != datetime.date.today():
        return None
    return reunion


@router.get("/{token}")
def checkin_page(token: str, request: Request, confirme: str | None = None, db: Session = Depends(get_db)):
    reunion = _reunion_du_jour(db, token)
    if not reunion:
        return templates.TemplateResponse(request, "checkin.html", {"reunion": None, "membres": []})

    presents_ids = {p.membre_id for p in reunion.presences if p.present}
    membres = (
        db.query(models.Membre)
        .filter(models.Membre.delegation_id == reunion.delegation_id)
        .order_by(models.Membre.full_name)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "checkin.html",
        {
            "reunion": reunion,
            "token": token,
            "membres": membres,
            "presents_ids": presents_ids,
            "confirme": confirme,
        },
    )


@router.post("/{token}")
def checkin_confirm(token: str, membre_id: int, db: Session = Depends(get_db)):
    reunion = _reunion_du_jour(db, token)
    if not reunion:
        return RedirectResponse(url=f"/checkin/{token}", status_code=status.HTTP_303_SEE_OTHER)

    membre = db.get(models.Membre, membre_id)
    if membre and membre.delegation_id == reunion.delegation_id:
        presence = (
            db.query(models.Presence)
            .filter(models.Presence.reunion_id == reunion.id, models.Presence.membre_id == membre_id)
            .first()
        )
        if presence:
            presence.present = True
        else:
            db.add(models.Presence(reunion_id=reunion.id, membre_id=membre_id, present=True))
        db.commit()

    return RedirectResponse(url=f"/checkin/{token}?confirme={membre_id}", status_code=status.HTTP_303_SEE_OTHER)
