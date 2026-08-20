"""Historique public des anciens présidents de la LECIM (photo, période, mot)."""

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from .. import models, schemas, storage
from ..database import get_db

router = APIRouter(prefix="/api/historique", tags=["historique"])

LOGO_PATH = Path(__file__).resolve().parent.parent / "static" / "img" / "logo.jpg"


@router.get("", response_model=list[schemas.HistoriqueOut])
def list_historique(db: Session = Depends(get_db)):
    return (
        db.query(models.HistoriquePresident)
        .filter(models.HistoriquePresident.is_published.is_(True))
        .order_by(models.HistoriquePresident.ordre, models.HistoriquePresident.id)
        .all()
    )


@router.get("/{president_id}/photo")
def historique_photo(president_id: int, db: Session = Depends(get_db)):
    president = db.get(models.HistoriquePresident, president_id)
    if president and president.is_published:
        stored = storage.get_stored_file(db, president.photo_path)
        if stored:
            return Response(content=stored.data, media_type=stored.content_type)
    return FileResponse(LOGO_PATH, media_type="image/jpeg")
