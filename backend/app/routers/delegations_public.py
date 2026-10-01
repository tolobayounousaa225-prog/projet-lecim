"""Annuaire public des délégations régionales de la LECIM — nom, région et quelques
indicateurs d'activité (écoles affiliées, réunions tenues, membres locaux), sans
exposer les informations internes (comptes, annonces) réservées au portail délégation."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/delegations", tags=["delegations-public"])


@router.get("", response_model=list[schemas.DelegationPublicOut])
def list_delegations(db: Session = Depends(get_db)):
    delegations = db.query(models.Delegation).order_by(models.Delegation.nom).all()
    return [
        schemas.DelegationPublicOut(
            id=d.id,
            nom=d.nom,
            region=d.region,
            ecoles_count=db.query(models.Etablissement)
            .filter(models.Etablissement.delegation_id == d.id)
            .count(),
            reunions_count=db.query(models.Reunion)
            .filter(models.Reunion.delegation_id == d.id)
            .count(),
            membres_count=db.query(models.Membre)
            .filter(models.Membre.delegation_id == d.id)
            .count(),
        )
        for d in delegations
    ]
