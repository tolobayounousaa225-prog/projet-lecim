"""Liste publique des partenaires actifs de la LECIM, affichée sur la vitrine."""

import mimetypes

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from .admin_files import UPLOAD_ROOT

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
    path = UPLOAD_ROOT / partenaire.logo_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="Logo introuvable")
    media_type = mimetypes.guess_type(partenaire.logo_path)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)
