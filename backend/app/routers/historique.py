"""Historique public des anciens présidents de la LECIM (photo, période, mot)."""

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from .admin_files import UPLOAD_ROOT

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
    if not president or not president.is_published or not president.photo_path:
        return FileResponse(LOGO_PATH, media_type="image/jpeg")
    path = UPLOAD_ROOT / president.photo_path
    media_type = mimetypes.guess_type(president.photo_path)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)
