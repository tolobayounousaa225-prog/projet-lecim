"""Membres fondateurs de la LECIM, affichés publiquement (photo, rôle, mot)."""

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from .admin_files import UPLOAD_ROOT

router = APIRouter(prefix="/api/fondateurs", tags=["fondateurs"])

LOGO_PATH = Path(__file__).resolve().parent.parent / "static" / "img" / "logo.jpg"


@router.get("", response_model=list[schemas.FondateurOut])
def list_fondateurs(db: Session = Depends(get_db)):
    return (
        db.query(models.MembreFondateur)
        .filter(models.MembreFondateur.is_published.is_(True))
        .order_by(models.MembreFondateur.ordre, models.MembreFondateur.id)
        .all()
    )


@router.get("/{fondateur_id}/photo")
def fondateur_photo(fondateur_id: int, db: Session = Depends(get_db)):
    fondateur = db.get(models.MembreFondateur, fondateur_id)
    if not fondateur or not fondateur.is_published or not fondateur.photo_path:
        return FileResponse(LOGO_PATH, media_type="image/jpeg")
    path = UPLOAD_ROOT / fondateur.photo_path
    media_type = mimetypes.guess_type(fondateur.photo_path)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)
