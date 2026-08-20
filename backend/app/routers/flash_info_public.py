"""Bande d'informations flash affichée en défilement sur toutes les pages du site
vitrine — voir FlashInfo dans models.py."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/flash-info", tags=["flash-info"])


@router.get("", response_model=list[schemas.FlashInfoOut])
def list_flash_info(db: Session = Depends(get_db)):
    return (
        db.query(models.FlashInfo)
        .filter(models.FlashInfo.is_active.is_(True))
        .order_by(models.FlashInfo.ordre, models.FlashInfo.id)
        .all()
    )
