from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models, storage
from ..config import settings
from ..database import get_db
from ..deps import require_documents_access_web, require_photos_access_web

router = APIRouter(prefix="/admin", tags=["admin-files"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Conservé pour les usages qui restent volontairement sur le disque éphémère
# du conteneur (ex. le cache d'images de partage régénérable de news.py) —
# les fichiers uploadés par l'admin, eux, sont désormais stockés en base de
# données (voir storage.py) et ne dépendent plus de UPLOAD_ROOT.
UPLOAD_ROOT = Path(__file__).resolve().parent.parent.parent / settings.upload_dir
DOCUMENTS_DIR = "documents"
PHOTOS_DIR = "photos"

ALLOWED_DOCUMENT_EXT = storage.ALLOWED_DOCUMENT_EXT
ALLOWED_PHOTO_EXT = storage.ALLOWED_PHOTO_EXT


# ---------- Documents / PV ----------

@router.get("/documents")
def documents_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_documents_access_web),
):
    items = db.query(models.Document).order_by(models.Document.created_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin/documents_list.html",
        {"admin": user, "items": items, "active": "documents"},
    )


@router.get("/documents/new")
def documents_new_form(
    request: Request,
    reunion_id: int | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_documents_access_web),
):
    reunions = db.query(models.Reunion).order_by(models.Reunion.date.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin/document_form.html",
        {
            "admin": user,
            "reunions": reunions,
            "selected_reunion_id": reunion_id,
            "active": "documents",
            "error": None,
        },
    )


@router.post("/documents/new")
async def documents_create(
    request: Request,
    title: str = Form(...),
    category: str = Form("pv"),
    reunion_id: str = Form(""),
    file: UploadFile = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_documents_access_web),
):
    try:
        stored_name, original_name = await storage.save_upload(db, file, DOCUMENTS_DIR, ALLOWED_DOCUMENT_EXT)
    except ValueError as exc:
        reunions = db.query(models.Reunion).order_by(models.Reunion.date.desc()).all()
        return templates.TemplateResponse(
            request,
            "admin/document_form.html",
            {
                "admin": user,
                "reunions": reunions,
                "active": "documents",
                "error": str(exc),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    document = models.Document(
        title=title,
        category=category if category in {"pv", "rapport", "autre"} else "autre",
        reunion_id=int(reunion_id) if reunion_id else None,
        file_path=f"documents/{stored_name}",
        original_filename=original_name,
        uploaded_by_id=user.id,
    )
    db.add(document)
    db.commit()
    return RedirectResponse(url="/admin/documents", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/documents/{document_id}/file")
def documents_file(
    document_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_documents_access_web),
):
    document = db.get(models.Document, document_id)
    if not document:
        return RedirectResponse(url="/admin/documents", status_code=status.HTTP_303_SEE_OTHER)
    stored = storage.get_stored_file(db, document.file_path)
    if not stored:
        return RedirectResponse(url="/admin/documents", status_code=status.HTTP_303_SEE_OTHER)
    return Response(
        content=stored.data,
        media_type=stored.content_type,
        headers={"Content-Disposition": f'attachment; filename="{document.original_filename}"'},
    )


@router.post("/documents/{document_id}/delete")
def documents_delete(
    document_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_documents_access_web),
):
    document = db.get(models.Document, document_id)
    if document:
        storage.delete_stored_file(db, document.file_path)
        db.delete(document)
        db.commit()
    return RedirectResponse(url="/admin/documents", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Galerie photo ----------

@router.get("/photos")
def photos_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_photos_access_web),
):
    items = db.query(models.Photo).order_by(models.Photo.created_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin/photos_list.html",
        {"admin": user, "items": items, "active": "photos"},
    )


@router.get("/photos/new")
def photos_new_form(
    request: Request,
    reunion_id: int | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_photos_access_web),
):
    reunions = db.query(models.Reunion).order_by(models.Reunion.date.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin/photo_form.html",
        {
            "admin": user,
            "reunions": reunions,
            "selected_reunion_id": reunion_id,
            "active": "photos",
            "error": None,
        },
    )


@router.post("/photos/new")
async def photos_create(
    request: Request,
    caption: str = Form(""),
    reunion_id: str = Form(""),
    is_public: bool = Form(False),
    file: UploadFile = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_photos_access_web),
):
    try:
        stored_name, original_name = await storage.save_upload(db, file, PHOTOS_DIR, ALLOWED_PHOTO_EXT)
    except ValueError as exc:
        reunions = db.query(models.Reunion).order_by(models.Reunion.date.desc()).all()
        return templates.TemplateResponse(
            request,
            "admin/photo_form.html",
            {
                "admin": user,
                "reunions": reunions,
                "active": "photos",
                "error": str(exc),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    photo = models.Photo(
        caption=caption or None,
        reunion_id=int(reunion_id) if reunion_id else None,
        file_path=f"photos/{stored_name}",
        original_filename=original_name,
        is_public=is_public,
        uploaded_by_id=user.id,
    )
    db.add(photo)
    db.commit()
    return RedirectResponse(url="/admin/photos", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/photos/{photo_id}/file")
def photos_file(
    photo_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_photos_access_web),
):
    photo = db.get(models.Photo, photo_id)
    if not photo:
        return RedirectResponse(url="/admin/photos", status_code=status.HTTP_303_SEE_OTHER)
    stored = storage.get_stored_file(db, photo.file_path)
    if not stored:
        return RedirectResponse(url="/admin/photos", status_code=status.HTTP_303_SEE_OTHER)
    return Response(content=stored.data, media_type=stored.content_type)


@router.post("/photos/{photo_id}/toggle-public")
def photos_toggle_public(
    photo_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_photos_access_web),
):
    photo = db.get(models.Photo, photo_id)
    if photo:
        photo.is_public = not photo.is_public
        db.commit()
    return RedirectResponse(url="/admin/photos", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/photos/{photo_id}/delete")
def photos_delete(
    photo_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_photos_access_web),
):
    photo = db.get(models.Photo, photo_id)
    if photo:
        storage.delete_stored_file(db, photo.file_path)
        db.delete(photo)
        db.commit()
    return RedirectResponse(url="/admin/photos", status_code=status.HTTP_303_SEE_OTHER)
