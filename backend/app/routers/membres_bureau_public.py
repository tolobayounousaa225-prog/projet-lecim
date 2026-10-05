"""Trombinoscope public du répertoire complet des membres du Bureau Exécutif National —
distinct de /api/gouvernance qui ne couvre que l'organigramme de direction (président,
vice-présidents, secrétariats). Ici : tout membre national (delegation_id NULL) ayant une
photo renseignée, sans notion de publication séparée (l'absence de photo suffit à exclure
un membre de la page publique)."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models, schemas, storage
from ..database import get_db

router = APIRouter(prefix="/api/membres-bureau", tags=["membres-bureau"])


@router.get("", response_model=list[schemas.MembreBureauOut])
def list_membres_bureau(db: Session = Depends(get_db)):
    return (
        db.query(models.Membre)
        .filter(models.Membre.delegation_id.is_(None), models.Membre.photo_path.isnot(None))
        .order_by(models.Membre.full_name)
        .all()
    )


@router.get("/{membre_id}/photo")
def membre_bureau_photo(membre_id: int, db: Session = Depends(get_db)):
    membre = db.get(models.Membre, membre_id)
    if not membre or not membre.photo_path:
        raise HTTPException(status_code=404, detail="Introuvable")
    stored = storage.get_stored_file(db, membre.photo_path)
    if not stored:
        raise HTTPException(status_code=404, detail="Photo introuvable")
    return Response(content=stored.data, media_type=stored.content_type)
