"""Membres fondateurs de la LECIM, affichés publiquement (photo, rôle, mot)."""

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from .. import models, schemas, storage
from ..database import get_db

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
    if fondateur and fondateur.is_published:
        stored = storage.get_stored_file(db, fondateur.photo_path)
        if stored:
            return Response(content=stored.data, media_type=stored.content_type)
    return FileResponse(LOGO_PATH, media_type="image/jpeg")
