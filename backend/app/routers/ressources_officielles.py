import mimetypes

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from .admin_files import UPLOAD_ROOT

router = APIRouter(prefix="/api/ressources-officielles", tags=["ressources-officielles"])


@router.get("", response_model=list[schemas.RessourceOfficielleOut])
def list_ressources_officielles(section: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.RessourceOfficielle).filter(models.RessourceOfficielle.is_published.is_(True))
    if section:
        query = query.filter(models.RessourceOfficielle.section == section)
    return query.order_by(
        models.RessourceOfficielle.ordre, models.RessourceOfficielle.created_at.desc()
    ).all()


@router.get("/{ressource_id}/photo")
def ressource_officielle_photo(ressource_id: int, db: Session = Depends(get_db)):
    ressource = db.get(models.RessourceOfficielle, ressource_id)
    if not ressource or not ressource.is_published:
        raise HTTPException(status_code=404, detail="Ressource introuvable")
    path = UPLOAD_ROOT / ressource.photo_path
    media_type = mimetypes.guess_type(ressource.photo_path)[0] or "image/jpeg"
    return FileResponse(path, media_type=media_type)


@router.get("/{ressource_id}/file")
def ressource_officielle_file(ressource_id: int, db: Session = Depends(get_db)):
    ressource = db.get(models.RessourceOfficielle, ressource_id)
    if not ressource or not ressource.is_published or not ressource.file_path:
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    path = UPLOAD_ROOT / ressource.file_path
    media_type = mimetypes.guess_type(ressource.original_filename or "")[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=ressource.original_filename)
