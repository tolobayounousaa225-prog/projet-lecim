from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .. import models, schemas, storage
from ..database import get_db
from ..deps import get_news_editor
from ..share_image import generate_news_share_image
from .admin_files import UPLOAD_ROOT

router = APIRouter(prefix="/api/news", tags=["news"])

NEWS_SHARE_DIR = UPLOAD_ROOT / "news_share"


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
    stored = storage.get_stored_file(db, news.image_path)
    if not stored:
        raise HTTPException(status_code=404, detail="Image introuvable")
    return Response(content=stored.data, media_type=stored.content_type)


@router.get("/{news_id}/share-image.png")
def news_share_image(news_id: int, db: Session = Depends(get_db)):
    news = db.get(models.NewsPost, news_id)
    if not news or not news.is_published:
        raise HTTPException(status_code=404, detail="Actualité introuvable")

    NEWS_SHARE_DIR.mkdir(parents=True, exist_ok=True)
    cached_path = NEWS_SHARE_DIR / f"{news_id}.png"
    is_stale = (
        not cached_path.exists()
        or cached_path.stat().st_mtime < news.updated_at.timestamp()
    )
    if is_stale:
        png_bytes = generate_news_share_image(news.title, news.published_at.strftime("%d/%m/%Y"))
        cached_path.write_bytes(png_bytes)

    return FileResponse(cached_path, media_type="image/png")


@router.get("/{news_id}", response_model=schemas.NewsOut)
def get_news(news_id: int, db: Session = Depends(get_db)):
    news = db.get(models.NewsPost, news_id)
    if not news or not news.is_published:
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
