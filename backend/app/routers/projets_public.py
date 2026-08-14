"""Liste publique des initiatives/projets de la LECIM, affichée sur la vitrine
(hors projets suspendus, non pertinents pour le public)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..models import PROJET_STATUTS

router = APIRouter(prefix="/api/projets", tags=["projets"])


@router.get("", response_model=list[schemas.ProjetPublicOut])
def list_projets(db: Session = Depends(get_db)):
    items = (
        db.query(models.Projet)
        .filter(models.Projet.statut != "suspendu")
        .order_by(models.Projet.created_at.desc())
        .all()
    )
    return [
        schemas.ProjetPublicOut(
            id=p.id,
            titre=p.titre,
            description=p.description,
            statut=p.statut,
            statut_label=PROJET_STATUTS.get(p.statut, p.statut),
        )
        for p in items
    ]
