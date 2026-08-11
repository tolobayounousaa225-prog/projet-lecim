"""Vérification publique d'authenticité d'une carte de membre (page ouverte au scan du QR code).

Aucune authentification requise — c'est le but : n'importe qui (agent de sécurité,
partenaire, etc.) doit pouvoir scanner une carte physique et vérifier son authenticité.
Seules les informations non sensibles sont exposées (pas le CNI, l'adresse, le contact
d'urgence ni les coordonnées personnelles, qui restent internes à la LECIM).
"""

import datetime
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from .admin_files import UPLOAD_ROOT

router = APIRouter(prefix="/verify", tags=["verify"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

VALID_STATUSES = {"validee", "imprimee", "disponible"}


def _check(carte: models.CarteMembre | None) -> str:
    if not carte or carte.status not in VALID_STATUSES:
        return "introuvable"
    if carte.date_validite and carte.date_validite < datetime.date.today():
        return "expiree"
    return "authentique"


@router.get("/{numero_carte}")
def verify_card(numero_carte: str, request: Request, db: Session = Depends(get_db)):
    carte = (
        db.query(models.CarteMembre)
        .filter(models.CarteMembre.numero_carte == numero_carte)
        .first()
    )
    result = _check(carte)
    return templates.TemplateResponse(
        request,
        "verify.html",
        {"carte": carte, "result": result, "numero_carte": numero_carte},
    )


@router.get("/{numero_carte}/photo")
def verify_card_photo(numero_carte: str, db: Session = Depends(get_db)):
    carte = (
        db.query(models.CarteMembre)
        .filter(models.CarteMembre.numero_carte == numero_carte)
        .first()
    )
    if _check(carte) == "introuvable" or not carte.photo_path:
        return FileResponse(
            Path(__file__).resolve().parent.parent / "static" / "img" / "logo.jpg",
            media_type="image/jpeg",
        )
    path = UPLOAD_ROOT / carte.photo_path
    media_type = mimetypes.guess_type(carte.photo_path)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)
