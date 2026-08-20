"""Calendrier scolaire national — dates communes (rentrée, vacances, examens) visibles
par toutes les écoles membres et sur la vitrine, distinct du calendrier interne des
réunions/activités du BEN."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/calendrier-scolaire", tags=["calendrier-scolaire"])


@router.get("", response_model=list[schemas.CalendrierScolaireOut])
def list_calendrier_scolaire(annee_scolaire: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.CalendrierScolaireEntry).filter(models.CalendrierScolaireEntry.is_published.is_(True))
    if annee_scolaire:
        query = query.filter(models.CalendrierScolaireEntry.annee_scolaire == annee_scolaire)
    return query.order_by(models.CalendrierScolaireEntry.date_debut).all()
