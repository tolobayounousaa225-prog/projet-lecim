"""Organigramme public du Bureau Exécutif National (photos des titulaires et adjoints)."""

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from .admin_files import UPLOAD_ROOT

router = APIRouter(prefix="/api/gouvernance", tags=["gouvernance"])

LOGO_PATH = Path(__file__).resolve().parent.parent / "static" / "img" / "logo.jpg"


@router.get("", response_model=list[schemas.GouvernanceOut])
def list_gouvernance(db: Session = Depends(get_db)):
    return (
        db.query(models.GouvernanceMembre)
        .filter(models.GouvernanceMembre.is_published.is_(True))
        .order_by(models.GouvernanceMembre.ordre, models.GouvernanceMembre.id)
        .all()
    )


def _serve_photo(path_value: str | None):
    if not path_value:
        raise HTTPException(status_code=404, detail="Photo introuvable")
    path = UPLOAD_ROOT / path_value
    media_type = mimetypes.guess_type(path_value)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)


@router.get("/{membre_id}/photo/titulaire")
def gouvernance_photo_titulaire(membre_id: int, db: Session = Depends(get_db)):
    membre = db.get(models.GouvernanceMembre, membre_id)
    if not membre or not membre.is_published:
        raise HTTPException(status_code=404, detail="Introuvable")
    return _serve_photo(membre.titulaire_photo_path)


@router.get("/{membre_id}/photo/adjoint")
def gouvernance_photo_adjoint(membre_id: int, db: Session = Depends(get_db)):
    membre = db.get(models.GouvernanceMembre, membre_id)
    if not membre or not membre.is_published:
        raise HTTPException(status_code=404, detail="Introuvable")
    return _serve_photo(membre.adjoint_photo_path)
