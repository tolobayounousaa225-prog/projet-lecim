"""Liste publique des partenaires actifs de la LECIM, affichée sur la vitrine."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/partenaires", tags=["partenaires"])


@router.get("", response_model=list[schemas.PartenairePublicOut])
def list_partenaires(db: Session = Depends(get_db)):
    return (
        db.query(models.Partenaire)
        .filter(models.Partenaire.statut == "actif")
        .order_by(models.Partenaire.nom)
        .all()
    )
