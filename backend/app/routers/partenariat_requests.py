"""Demande de partenariat déposée en libre-service depuis la vitrine — crée un
partenaire au statut "en discussion", invisible publiquement tant que le BEN ne
l'a pas validé (passage à "actif") depuis /admin/partenaires."""

import datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..models import PARTENAIRE_TYPES

router = APIRouter(prefix="/api/partenariat-requests", tags=["partenariat"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_partenariat_request(payload: schemas.PartenariatRequestCreate, db: Session = Depends(get_db)):
    projet = db.get(models.Projet, payload.projet_id) if payload.projet_id else None

    notes = (
        f"Demande de partenariat reçue via le site le {datetime.date.today().isoformat()}.\n\n"
    )
    if projet:
        notes += f"Concerne le projet : {projet.titre}\n\n"
    notes += f"Message :\n{payload.message}"

    partenaire = models.Partenaire(
        nom=payload.nom,
        type=payload.type if payload.type in PARTENAIRE_TYPES else "autre",
        pays=payload.pays or None,
        contact_nom=payload.contact_nom,
        contact_email=payload.contact_email,
        contact_telephone=payload.contact_telephone or None,
        statut="en_discussion",
        notes=notes,
        projet_id=projet.id if projet else None,
    )
    db.add(partenaire)
    db.commit()
    return {"ok": True}
