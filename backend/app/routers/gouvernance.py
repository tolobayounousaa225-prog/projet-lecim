"""Organigramme public du Bureau Exécutif National (photos des titulaires et adjoints)."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models, schemas, storage
from ..database import get_db

router = APIRouter(prefix="/api/gouvernance", tags=["gouvernance"])


@router.get("", response_model=list[schemas.GouvernanceOut])
def list_gouvernance(db: Session = Depends(get_db)):
    return (
        db.query(models.GouvernanceMembre)
        .filter(models.GouvernanceMembre.is_published.is_(True))
        .order_by(models.GouvernanceMembre.ordre, models.GouvernanceMembre.id)
        .all()
    )


def _serve_photo(db: Session, path_value: str | None):
    stored = storage.get_stored_file(db, path_value)
    if not stored:
        raise HTTPException(status_code=404, detail="Photo introuvable")
    return Response(content=stored.data, media_type=stored.content_type)


@router.get("/{membre_id}/photo/titulaire")
def gouvernance_photo_titulaire(membre_id: int, db: Session = Depends(get_db)):
    membre = db.get(models.GouvernanceMembre, membre_id)
    if not membre or not membre.is_published:
        raise HTTPException(status_code=404, detail="Introuvable")
    return _serve_photo(db, membre.titulaire_photo_path)


@router.get("/{membre_id}/photo/adjoint")
def gouvernance_photo_adjoint(membre_id: int, db: Session = Depends(get_db)):
    membre = db.get(models.GouvernanceMembre, membre_id)
    if not membre or not membre.is_published:
        raise HTTPException(status_code=404, detail="Introuvable")
    return _serve_photo(db, membre.adjoint_photo_path)
