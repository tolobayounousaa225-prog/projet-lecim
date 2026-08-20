"""Page de partage server-rendue pour une actualité — sert des balises Open
Graph correctes par article. Le site vitrine (actualite.html) est une page
qui charge son contenu en JavaScript côté client : les robots des réseaux
sociaux (WhatsApp, Facebook, Twitter) ne l'exécutent pas et ne verraient donc
qu'un aperçu générique identique pour tous les articles. Cette page,
elle, est rendue côté serveur avec les bonnes balises par article, puis
redirige immédiatement le visiteur humain vers la page complète."""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..database import get_db

router = APIRouter(tags=["actualite-share"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/actualite/{news_id}", response_class=HTMLResponse)
def actualite_share_page(news_id: int, request: Request, db: Session = Depends(get_db)):
    news = db.get(models.NewsPost, news_id)
    if not news or not news.is_published:
        return templates.TemplateResponse(
            request,
            "actualite_share.html",
            {"found": False, "redirect_url": f"{settings.vitrine_base_url}/actualites.html"},
        )
    return templates.TemplateResponse(
        request,
        "actualite_share.html",
        {
            "found": True,
            "title": news.title,
            "description": news.excerpt,
            "image_url": f"{settings.public_base_url}/api/news/{news_id}/share-image.png",
            "page_url": f"{settings.public_base_url}/actualite/{news_id}",
            "redirect_url": f"{settings.vitrine_base_url}/actualite.html?id={news_id}",
        },
    )
