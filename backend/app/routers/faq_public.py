"""Foire aux questions publique."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/faq", tags=["faq"])


@router.get("", response_model=list[schemas.FaqOut])
def list_faq(db: Session = Depends(get_db)):
    return (
        db.query(models.Faq)
        .filter(models.Faq.is_published.is_(True))
        .order_by(models.Faq.ordre, models.Faq.id)
        .all()
    )
