"""Vérification publique des attestations (affiliation établissement, appartenance BEN),
ouverte au scan du QR code — même philosophie que /verify et /verify-eleve : aucune
authentification requise, aucune donnée personnelle sensible exposée."""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..attestations_pdf import numero_affiliation
from ..database import get_db

router = APIRouter(tags=["verify"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/verify-etablissement/{etablissement_id}")
def verify_etablissement(etablissement_id: int, request: Request, db: Session = Depends(get_db)):
    etablissement = db.get(models.Etablissement, etablissement_id)
    return templates.TemplateResponse(
        request,
        "verify_etablissement.html",
        {
            "etablissement": etablissement,
            "found": etablissement is not None,
            "numero": numero_affiliation(etablissement_id),
        },
    )


@router.get("/verify-membre/{user_id}")
def verify_membre(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = db.get(models.User, user_id)
    is_ben_member = (
        user is not None
        and not user.is_delegation_account
        and not user.is_etablissement_account
    )
    return templates.TemplateResponse(
        request,
        "verify_membre.html",
        {"user": user if is_ben_member else None, "found": is_ben_member},
    )
