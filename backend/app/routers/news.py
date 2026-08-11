import mimetypes

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_news_editor
from .admin_files import UPLOAD_ROOT

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("", response_model=list[schemas.NewsOut])
def list_news(limit: int = 20, db: Session = Depends(get_db)):
    return (
        db.query(models.NewsPost)
        .filter(models.NewsPost.is_published.is_(True))
        .order_by(desc(models.NewsPost.published_at))
        .limit(limit)
        .all()
    )


@router.get("/{news_id}/image")
def news_image(news_id: int, db: Session = Depends(get_db)):
    news = db.get(models.NewsPost, news_id)
    if not news or not news.is_published or not news.image_path:
        raise HTTPException(status_code=404, detail="Image introuvable")
    path = UPLOAD_ROOT / news.image_path
    media_type = mimetypes.guess_type(news.image_path)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)


@router.get("/{news_id}", response_model=schemas.NewsOut)
def get_news(news_id: int, db: Session = Depends(get_db)):
    news = db.get(models.NewsPost, news_id)
    if not news:
        raise HTTPException(status_code=404, detail="Actualité introuvable")
    return news


@router.post("", response_model=schemas.NewsOut, status_code=status.HTTP_201_CREATED)
def create_news(
    payload: schemas.NewsCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_news_editor),
):
    news = models.NewsPost(**payload.model_dump())
    db.add(news)
    db.commit()
    db.refresh(news)
    return news


@router.put("/{news_id}", response_model=schemas.NewsOut)
def update_news(
    news_id: int,
    payload: schemas.NewsUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_news_editor),
):
    news = db.get(models.NewsPost, news_id)
    if not news:
        raise HTTPException(status_code=404, detail="Actualité introuvable")
    for field, value in payload.model_dump().items():
        setattr(news, field, value)
    db.commit()
    db.refresh(news)
    return news


@router.delete("/{news_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_news(
    news_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_news_editor),
):
    news = db.get(models.NewsPost, news_id)
    if not news:
        raise HTTPException(status_code=404, detail="Actualité introuvable")
    db.delete(news)
    db.commit()
