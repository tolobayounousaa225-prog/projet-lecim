import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_publications_access_web
from ..models import PUBLICATION_CATEGORIES
from .admin_files import ALLOWED_DOCUMENT_EXT, ALLOWED_PHOTO_EXT, UPLOAD_ROOT, _save_upload

router = APIRouter(prefix="/admin/publications", tags=["admin-publications"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

PUBLICATIONS_DIR = UPLOAD_ROOT / "publications"
ALLOWED_PUBLICATION_EXT = ALLOWED_DOCUMENT_EXT | ALLOWED_PHOTO_EXT


@router.get("")
def publications_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    items = db.query(models.PublicationPublique).order_by(models.PublicationPublique.published_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin/publications_list.html",
        {"admin": user, "items": items, "categories": PUBLICATION_CATEGORIES, "active": "publications"},
    )


@router.get("/new")
def publications_new_form(
    request: Request,
    user: models.User = Depends(require_publications_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/publication_form.html",
        {
            "admin": user,
            "categories": PUBLICATION_CATEGORIES,
            "today": datetime.date.today(),
            "active": "publications",
            "error": None,
        },
    )


@router.post("/new")
async def publications_create(
    request: Request,
    title: str = Form(...),
    category: str = Form("autre"),
    description: str = Form(""),
    published_at: datetime.date = Form(...),
    is_published: bool = Form(False),
    file: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    try:
        stored_name, original_name = await _save_upload(file, PUBLICATIONS_DIR, ALLOWED_PUBLICATION_EXT)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "admin/publication_form.html",
            {
                "admin": user,
                "categories": PUBLICATION_CATEGORIES,
                "today": datetime.date.today(),
                "active": "publications",
                "error": str(exc),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    publication = models.PublicationPublique(
        title=title,
        category=category if category in PUBLICATION_CATEGORIES else "autre",
        description=description or None,
        file_path=f"publications/{stored_name}",
        original_filename=original_name,
        published_at=published_at,
        is_published=is_published,
        uploaded_by_id=user.id,
    )
    db.add(publication)
    db.commit()
    return RedirectResponse(url="/admin/publications", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{publication_id}/delete")
def publications_delete(
    publication_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    publication = db.get(models.PublicationPublique, publication_id)
    if publication:
        path = UPLOAD_ROOT / publication.file_path
        db.delete(publication)
        db.commit()
        if path.exists():
            path.unlink()
    return RedirectResponse(url="/admin/publications", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{publication_id}/toggle")
def publications_toggle(
    publication_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    publication = db.get(models.PublicationPublique, publication_id)
    if publication:
        publication.is_published = not publication.is_published
        db.commit()
    return RedirectResponse(url="/admin/publications", status_code=status.HTTP_303_SEE_OTHER)
