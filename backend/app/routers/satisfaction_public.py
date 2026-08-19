"""Réponse publique à un sondage de satisfaction post-réunion/formation — accessible
via un jeton non devinable envoyé par e-mail aux participants, sans authentification.
Réponses anonymes : aucune donnée personnelle du répondant n'est enregistrée."""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(tags=["satisfaction"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/sondage-satisfaction/{token}")
def satisfaction_form(token: str, request: Request, db: Session = Depends(get_db)):
    sondage = db.query(models.SondageSatisfaction).filter(models.SondageSatisfaction.token == token).first()
    return templates.TemplateResponse(
        request,
        "satisfaction_form.html",
        {"sondage": sondage, "token": token, "envoye": False},
    )


@router.post("/sondage-satisfaction/{token}")
def satisfaction_submit(
    token: str,
    request: Request,
    note: int = Form(...),
    commentaire: str = Form(""),
    db: Session = Depends(get_db),
):
    sondage = db.query(models.SondageSatisfaction).filter(models.SondageSatisfaction.token == token).first()
    if sondage and 1 <= note <= 5:
        db.add(models.SondageSatisfactionReponse(sondage_id=sondage.id, note=note, commentaire=commentaire or None))
        db.commit()
    return templates.TemplateResponse(
        request,
        "satisfaction_form.html",
        {"sondage": sondage, "token": token, "envoye": True},
    )
