"""Membres du Conseil d'administration de la LECIM, affichés publiquement (photo, rôle, mot)."""

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from .admin_files import UPLOAD_ROOT

router = APIRouter(prefix="/api/conseil-administration", tags=["conseil-administration"])

LOGO_PATH = Path(__file__).resolve().parent.parent / "static" / "img" / "logo.jpg"


@router.get("", response_model=list[schemas.ConseilAdministrationOut])
def list_conseil_administration(db: Session = Depends(get_db)):
    return (
        db.query(models.MembreConseilAdministration)
        .filter(models.MembreConseilAdministration.is_published.is_(True))
        .order_by(models.MembreConseilAdministration.ordre, models.MembreConseilAdministration.id)
        .all()
    )


@router.get("/{membre_id}/photo")
def conseil_administration_photo(membre_id: int, db: Session = Depends(get_db)):
    membre = db.get(models.MembreConseilAdministration, membre_id)
    if not membre or not membre.is_published or not membre.photo_path:
        return FileResponse(LOGO_PATH, media_type="image/jpeg")
    path = UPLOAD_ROOT / membre.photo_path
    media_type = mimetypes.guess_type(membre.photo_path)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)
