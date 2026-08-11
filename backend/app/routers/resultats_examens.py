"""Résultats publics aux examens scolaires islamiques, par établissement et année scolaire."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/resultats-examens", tags=["resultats-examens"])


@router.get("", response_model=list[schemas.ResultatExamenOut])
def list_resultats(
    etablissement_id: int | None = None,
    annee_scolaire: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.ResultatExamen).filter(models.ResultatExamen.is_published.is_(True))
    if etablissement_id:
        query = query.filter(models.ResultatExamen.etablissement_id == etablissement_id)
    if annee_scolaire:
        query = query.filter(models.ResultatExamen.annee_scolaire == annee_scolaire)
    return query.order_by(models.ResultatExamen.annee_scolaire.desc()).all()
