"""Liste publique des partenaires actifs de la LECIM, affichée sur la vitrine."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models, schemas, storage
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


@router.get("/{partenaire_id}/logo")
def partenaire_logo(partenaire_id: int, db: Session = Depends(get_db)):
    partenaire = db.get(models.Partenaire, partenaire_id)
    if not partenaire or not partenaire.logo_path:
        raise HTTPException(status_code=404, detail="Logo introuvable")
    stored = storage.get_stored_file(db, partenaire.logo_path)
    if not stored:
        raise HTTPException(status_code=404, detail="Logo introuvable")
    return Response(content=stored.data, media_type=stored.content_type)
