"""Carte interactive publique : localisation des établissements affiliés et des
délégations régionales ayant renseigné leurs coordonnées géographiques."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/carte", tags=["carte"])


@router.get("", response_model=list[schemas.CarteMarkerOut])
def list_markers(db: Session = Depends(get_db)):
    markers: list[schemas.CarteMarkerOut] = []

    etablissements = (
        db.query(models.Etablissement)
        .filter(models.Etablissement.latitude.isnot(None), models.Etablissement.longitude.isnot(None))
        .all()
    )
    for e in etablissements:
        markers.append(
            schemas.CarteMarkerOut(
                type="etablissement",
                nom=e.nom,
                detail=e.bureau_local,
                latitude=e.latitude,
                longitude=e.longitude,
            )
        )

    delegations = (
        db.query(models.Delegation)
        .filter(models.Delegation.latitude.isnot(None), models.Delegation.longitude.isnot(None))
        .all()
    )
    for d in delegations:
        markers.append(
            schemas.CarteMarkerOut(
                type="delegation",
                nom=d.nom,
                detail=d.region,
                latitude=d.latitude,
                longitude=d.longitude,
            )
        )

    return markers
