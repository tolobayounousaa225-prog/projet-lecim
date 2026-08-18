"""Statistiques de fréquentation de la vitrine — respectueuses de la vie privée :
un compteur agrégé par page et par jour, sans IP, cookie ni identifiant de
visiteur jamais enregistré."""

import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/api/stats", tags=["stats"])


class PageViewIn(BaseModel):
    path: str


@router.post("/view", status_code=204)
def record_page_view(payload: PageViewIn, db: Session = Depends(get_db)):
    path = (payload.path or "/").strip()[:300] or "/"
    today = datetime.date.today()
    try:
        row = (
            db.query(models.PageView)
            .filter(models.PageView.path == path, models.PageView.date == today)
            .with_for_update()
            .first()
        )
        if row:
            row.views += 1
        else:
            db.add(models.PageView(path=path, date=today, views=1))
        db.commit()
    except Exception:
        db.rollback()
    return None
