import mimetypes

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from .admin_files import UPLOAD_ROOT

router = APIRouter(prefix="/api/publications", tags=["publications"])


@router.get("", response_model=list[schemas.PublicationOut])
def list_publications(db: Session = Depends(get_db)):
    return (
        db.query(models.PublicationPublique)
        .filter(models.PublicationPublique.is_published.is_(True))
        .order_by(models.PublicationPublique.published_at.desc())
        .all()
    )


@router.get("/{publication_id}/file")
def publication_file(publication_id: int, db: Session = Depends(get_db)):
    publication = db.get(models.PublicationPublique, publication_id)
    if not publication or not publication.is_published:
        raise HTTPException(status_code=404, detail="Document introuvable")
    path = UPLOAD_ROOT / publication.file_path
    media_type = mimetypes.guess_type(publication.original_filename)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=publication.original_filename)
