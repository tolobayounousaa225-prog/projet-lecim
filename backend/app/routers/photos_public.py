"""Galerie photo publique — uniquement les photos explicitement publiées par
l'administrateur (is_public=True), le reste de la galerie restant interne."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .. import models, schemas, storage
from ..database import get_db

router = APIRouter(prefix="/api/photos", tags=["photos"])


@router.get("", response_model=list[schemas.PhotoPublicOut])
def list_public_photos(db: Session = Depends(get_db)):
    return (
        db.query(models.Photo)
        .filter(models.Photo.is_public.is_(True))
        .order_by(desc(models.Photo.created_at))
        .all()
    )


@router.get("/{photo_id}/image")
def photo_image(photo_id: int, db: Session = Depends(get_db)):
    photo = db.get(models.Photo, photo_id)
    if not photo or not photo.is_public:
        raise HTTPException(status_code=404, detail="Photo introuvable")
    stored = storage.get_stored_file(db, photo.file_path)
    if not stored:
        raise HTTPException(status_code=404, detail="Photo introuvable")
    return Response(content=stored.data, media_type=stored.content_type)
