"""Témoignages d'écoles membres, affichés publiquement (photo, rôle, texte)."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models, schemas, storage
from ..database import get_db

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
    stored = storage.get_stored_file(db, temoignage.photo_path)
    if not stored:
        raise HTTPException(status_code=404, detail="Introuvable")
    return Response(content=stored.data, media_type=stored.content_type)
