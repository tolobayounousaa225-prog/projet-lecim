"""Micro-sondages anonymes de la vitrine (avis du grand public, distinct des
sondages du BEN réservés aux membres connectés)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/sondages-express", tags=["sondages-express"])


@router.get("/actif", response_model=schemas.SondageExpressOut | None)
def sondage_express_actif(db: Session = Depends(get_db)):
    return (
        db.query(models.SondageExpress)
        .filter(models.SondageExpress.is_active.is_(True))
        .order_by(models.SondageExpress.created_at.desc())
        .first()
    )


@router.post("/{sondage_id}/vote")
def sondage_express_vote(sondage_id: int, payload: schemas.SondageExpressVoteIn, db: Session = Depends(get_db)):
    sondage = db.get(models.SondageExpress, sondage_id)
    if not sondage or not sondage.is_active:
        raise HTTPException(status_code=404, detail="Sondage introuvable ou clos")
    option = (
        db.query(models.SondageExpressOption)
        .filter(
            models.SondageExpressOption.id == payload.option_id,
            models.SondageExpressOption.sondage_id == sondage_id,
        )
        .with_for_update()
        .first()
    )
    if not option:
        raise HTTPException(status_code=404, detail="Option introuvable")
    option.votes += 1
    db.commit()
    db.refresh(sondage)
    return sondage
