"""Déclaration de don en libre-service depuis la vitrine — le versement est
effectué hors ligne (virement/dépôt) puis simplement déclaré ici pour que le
BEN puisse le rapprocher de son relevé bancaire."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/dons", tags=["dons"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_don(payload: schemas.DonDeclareCreate, db: Session = Depends(get_db)):
    don = models.DonDeclare(
        nom_donateur=payload.nom_donateur,
        email=payload.email,
        telephone=payload.telephone,
        montant=payload.montant,
        date_don=payload.date_don,
        message=payload.message,
    )
    db.add(don)
    db.commit()
    return {"ok": True}
