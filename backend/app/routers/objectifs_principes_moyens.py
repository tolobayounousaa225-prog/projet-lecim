"""Objectifs, principes et moyens de la LECIM — section publique de la page À propos."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/objectifs-principes-moyens", tags=["objectifs-principes-moyens"])


@router.get("", response_model=list[schemas.ObjectifPrincipeMoyenOut])
def list_objectifs_principes_moyens(db: Session = Depends(get_db)):
    return (
        db.query(models.ObjectifPrincipeMoyen)
        .filter(models.ObjectifPrincipeMoyen.is_published.is_(True))
        .order_by(models.ObjectifPrincipeMoyen.categorie, models.ObjectifPrincipeMoyen.ordre, models.ObjectifPrincipeMoyen.id)
        .all()
    )
