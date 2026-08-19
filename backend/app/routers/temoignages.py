"""Témoignages d'écoles membres, affichés publiquement (photo, rôle, texte)."""

import mimetypes

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from .admin_files import UPLOAD_ROOT

router = APIRouter(prefix="/api/temoignages", tags=["temoignages"])


@router.get("", response_model=list[schemas.TemoignageOut])
def list_temoignages(db: Session = Depends(get_db)):
    return (
        db.query(models.Temoignage)
        .filter(models.Temoignage.is_published.is_(True))
        .order_by(models.Temoignage.ordre, models.Temoignage.id)
        .all()
    )


@router.get("/{temoignage_id}/photo")
def temoignage_photo(temoignage_id: int, db: Session = Depends(get_db)):
    temoignage = db.get(models.Temoignage, temoignage_id)
    if not temoignage or not temoignage.is_published or not temoignage.photo_path:
        raise HTTPException(status_code=404, detail="Introuvable")
    path = UPLOAD_ROOT / temoignage.photo_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="Introuvable")
    media_type = mimetypes.guess_type(temoignage.photo_path)[0] or "image/jpeg"
    return FileResponse(path, media_type=media_type)
