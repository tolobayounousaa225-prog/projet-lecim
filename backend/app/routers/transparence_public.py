"""Tableau de transparence publique : totaux financiers agrégés par année scolaire,
sans aucun détail par transaction ni par établissement — seulement des sommes
globales, dans un but de confiance envers les écoles membres et le public."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..reports import multi_year_financial_summary

router = APIRouter(prefix="/api/transparence", tags=["transparence"])


@router.get("", response_model=list[schemas.TransparenceAnneeOut])
def transparence(db: Session = Depends(get_db)):
    return multi_year_financial_summary(db)
