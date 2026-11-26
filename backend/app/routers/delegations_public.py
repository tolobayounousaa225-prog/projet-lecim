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
    out = []
    for d in delegations:
        titulaire = (
            db.query(models.User)
            .filter(models.User.delegation_id == d.id, models.User.is_delegation_titulaire.is_(True))
            .first()
        )
        out.append(
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
                responsable_nom=titulaire.full_name if titulaire else None,
                responsable_fonction=(titulaire.role_local or "Président du Bureau Local") if titulaire else None,
            )
        )
    return out
