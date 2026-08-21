import re
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_publications_access_web

router = APIRouter(prefix="/admin/videos", tags=["admin-videos"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

_YOUTUBE_URL_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)
_YOUTUBE_BARE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _extract_youtube_id(raw: str) -> str | None:
    raw = raw.strip()
    if _YOUTUBE_BARE_ID_RE.match(raw):
        return raw
    match = _YOUTUBE_URL_RE.search(raw)
    return match.group(1) if match else None


@router.get("")
def videos_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    items = db.query(models.VideoPublic).order_by(models.VideoPublic.ordre, models.VideoPublic.id).all()
    return templates.TemplateResponse(
        request,
        "admin/videos_list.html",
        {"admin": user, "items": items, "active": "videos"},
    )


@router.post("/new")
def videos_create(
    request: Request,
    titre: str = Form(...),
    lien: str = Form(...),
    description: str = Form(""),
    ordre: int = Form(0),
    is_published: bool = Form(False),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    youtube_id = _extract_youtube_id(lien)
    if not youtube_id:
        items = db.query(models.VideoPublic).order_by(models.VideoPublic.ordre, models.VideoPublic.id).all()
        return templates.TemplateResponse(
            request,
            "admin/videos_list.html",
            {
                "admin": user, "items": items, "active": "videos",
                "error": "Lien YouTube non reconnu — collez l'URL complète de la vidéo (ex. https://www.youtube.com/watch?v=...).",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    db.add(
        models.VideoPublic(
            titre=titre, description=description or None, youtube_id=youtube_id,
            ordre=ordre, is_published=is_published, created_by_id=user.id,
        )
    )
    db.commit()
    return RedirectResponse(url="/admin/videos", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{video_id}/edit")
def videos_edit_form(
    video_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    item = db.get(models.VideoPublic, video_id)
    if not item:
        return RedirectResponse(url="/admin/videos", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request,
        "admin/video_form.html",
        {"admin": user, "item": item, "active": "videos", "error": None},
    )


@router.post("/{video_id}/edit")
def videos_update(
    video_id: int,
    request: Request,
    titre: str = Form(...),
    lien: str = Form(...),
    description: str = Form(""),
    ordre: int = Form(0),
    is_published: bool = Form(False),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    item = db.get(models.VideoPublic, video_id)
    if not item:
        return RedirectResponse(url="/admin/videos", status_code=status.HTTP_303_SEE_OTHER)
    youtube_id = _extract_youtube_id(lien)
    if not youtube_id:
        return templates.TemplateResponse(
            request,
            "admin/video_form.html",
            {
                "admin": user, "item": item, "active": "videos",
                "error": "Lien YouTube non reconnu — collez l'URL complète de la vidéo (ex. https://www.youtube.com/watch?v=...).",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    item.titre = titre
    item.description = description or None
    item.youtube_id = youtube_id
    item.ordre = ordre
    item.is_published = is_published
    db.commit()
    return RedirectResponse(url="/admin/videos", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{video_id}/toggle")
def videos_toggle(
    video_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    item = db.get(models.VideoPublic, video_id)
    if item:
        item.is_published = not item.is_published
        db.commit()
    return RedirectResponse(url="/admin/videos", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{video_id}/delete")
def videos_delete(
    video_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    item = db.get(models.VideoPublic, video_id)
    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse(url="/admin/videos", status_code=status.HTTP_303_SEE_OTHER)
