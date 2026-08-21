"""Vidéothèque publique — vidéos hébergées sur YouTube, voir VideoPublic dans models.py."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/videos", tags=["videos"])


@router.get("", response_model=list[schemas.VideoPublicOut])
def list_videos(db: Session = Depends(get_db)):
    return (
        db.query(models.VideoPublic)
        .filter(models.VideoPublic.is_published.is_(True))
        .order_by(models.VideoPublic.ordre, models.VideoPublic.id)
        .all()
    )
