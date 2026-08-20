"""Membres du Conseil d'administration de la LECIM, affichés publiquement (photo, rôle, mot)."""

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from .. import models, schemas, storage
from ..database import get_db

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
    if membre and membre.is_published:
        stored = storage.get_stored_file(db, membre.photo_path)
        if stored:
            return Response(content=stored.data, media_type=stored.content_type)
    return FileResponse(LOGO_PATH, media_type="image/jpeg")
