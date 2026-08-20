"""Contenu texte et images personnalisés du site vitrine (voir site_content_fields.py)."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models, storage
from ..database import get_db
from ..site_content_fields import SITE_CONTENT_FIELDS

router = APIRouter(prefix="/api/site-content", tags=["site-content"])


@router.get("")
def get_site_content(db: Session = Depends(get_db)) -> dict[str, str]:
    rows = db.query(models.SiteContent).filter(models.SiteContent.value.isnot(None)).all()
    result: dict[str, str] = {}
    for r in rows:
        if not r.value:
            continue
        meta = SITE_CONTENT_FIELDS.get(r.key)
        if meta and meta.get("type") == "image":
            result[r.key] = f"/api/site-content/{r.key}/image"
        else:
            result[r.key] = r.value
    return result


@router.get("/{key}/image")
def site_content_image(key: str, db: Session = Depends(get_db)):
    meta = SITE_CONTENT_FIELDS.get(key)
    if not meta or meta.get("type") != "image":
        raise HTTPException(status_code=404, detail="Introuvable")
    row = db.get(models.SiteContent, key)
    if not row or not row.value:
        raise HTTPException(status_code=404, detail="Image introuvable")
    stored = storage.get_stored_file(db, row.value)
    if not stored:
        raise HTTPException(status_code=404, detail="Image introuvable")
    return Response(content=stored.data, media_type=stored.content_type)
