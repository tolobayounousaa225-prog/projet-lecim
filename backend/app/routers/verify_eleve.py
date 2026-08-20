"""Vérification publique d'authenticité d'une carte scolaire (page ouverte au scan du QR code).

Aucune authentification requise, comme pour /verify (carte de membre du BEN) — seules les
informations qui figurent déjà sur la carte physique (nom, classe, établissement, photo,
matricule, validité) sont exposées. Rien de plus sensible n'est publié."""

import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models, storage
from ..database import get_db
from ..rate_limit import rate_limiter

router = APIRouter(prefix="/verify-eleve", tags=["verify"], dependencies=[Depends(rate_limiter("verify-eleve", 30, 60))])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

VALID_STATUSES = {"validee", "imprimee", "disponible"}


def _check(carte: models.CarteScolaire | None) -> str:
    if not carte or carte.status not in VALID_STATUSES:
        return "introuvable"
    if carte.date_validite and carte.date_validite < datetime.date.today():
        return "expiree"
    return "authentique"


@router.get("/{matricule}")
def verify_carte_eleve(matricule: str, request: Request, db: Session = Depends(get_db)):
    carte = (
        db.query(models.CarteScolaire)
        .filter(models.CarteScolaire.matricule == matricule)
        .first()
    )
    result = _check(carte)
    return templates.TemplateResponse(
        request,
        "verify_eleve.html",
        {"carte": carte, "result": result, "matricule": matricule},
    )


@router.get("/{matricule}/photo")
def verify_carte_eleve_photo(matricule: str, db: Session = Depends(get_db)):
    carte = (
        db.query(models.CarteScolaire)
        .filter(models.CarteScolaire.matricule == matricule)
        .first()
    )
    if _check(carte) != "introuvable" and carte.photo_path:
        stored = storage.get_stored_file(db, carte.photo_path)
        if stored:
            return Response(content=stored.data, media_type=stored.content_type)
    return FileResponse(
        Path(__file__).resolve().parent.parent / "static" / "img" / "logo.jpg",
        media_type="image/jpeg",
    )
