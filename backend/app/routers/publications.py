from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models, schemas, storage
from ..database import get_db

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
    stored = storage.get_stored_file(db, publication.file_path)
    if not stored:
        raise HTTPException(status_code=404, detail="Document introuvable")
    return Response(
        content=stored.data,
        media_type=stored.content_type,
        headers={"Content-Disposition": f'attachment; filename="{publication.original_filename}"'},
    )
