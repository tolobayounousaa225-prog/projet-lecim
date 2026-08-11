"""Contenu texte personnalisé du site vitrine (voir site_content_fields.py)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/api/site-content", tags=["site-content"])


@router.get("")
def get_site_content(db: Session = Depends(get_db)) -> dict[str, str]:
    rows = db.query(models.SiteContent).filter(models.SiteContent.value.isnot(None)).all()
    return {r.key: r.value for r in rows if r.value}
