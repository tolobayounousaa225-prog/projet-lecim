from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models, schemas, storage
from ..database import get_db

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
    stored = storage.get_stored_file(db, ressource.photo_path)
    if not stored:
        raise HTTPException(status_code=404, detail="Photo introuvable")
    return Response(content=stored.data, media_type=stored.content_type)


@router.get("/{ressource_id}/file")
def ressource_officielle_file(ressource_id: int, db: Session = Depends(get_db)):
    ressource = db.get(models.RessourceOfficielle, ressource_id)
    if not ressource or not ressource.is_published or not ressource.file_path:
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    stored = storage.get_stored_file(db, ressource.file_path)
    if not stored:
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    return Response(
        content=stored.data,
        media_type=stored.content_type,
        headers={"Content-Disposition": f'attachment; filename="{ressource.original_filename}"'},
    )
