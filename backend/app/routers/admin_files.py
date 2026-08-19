import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..database import get_db
from ..deps import require_documents_access_web, require_photos_access_web

router = APIRouter(prefix="/admin", tags=["admin-files"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

UPLOAD_ROOT = Path(__file__).resolve().parent.parent.parent / settings.upload_dir
DOCUMENTS_DIR = UPLOAD_ROOT / "documents"
PHOTOS_DIR = UPLOAD_ROOT / "photos"

ALLOWED_DOCUMENT_EXT = {".pdf", ".doc", ".docx", ".odt"}
ALLOWED_PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_UPLOAD_BYTES = settings.max_upload_size_mb * 1024 * 1024


async def _save_upload(file: UploadFile | None, dest_dir: Path, allowed_ext: set[str]) -> tuple[str, str]:
    if file is None or not file.filename:
        raise ValueError("Aucun fichier fourni")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed_ext:
        raise ValueError(f"Extension non autorisée : {ext}")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Fichier trop volumineux")
    stored_name = f"{uuid.uuid4().hex}{ext}"
    dest_path = dest_dir / stored_name
    dest_path.write_bytes(data)
    return stored_name, (file.filename or stored_name)


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
        stored_name, original_name = await _save_upload(file, DOCUMENTS_DIR, ALLOWED_DOCUMENT_EXT)
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
    path = UPLOAD_ROOT / document.file_path
    if not path.exists():
        return RedirectResponse(url="/admin/documents", status_code=status.HTTP_303_SEE_OTHER)
    media_type = mimetypes.guess_type(document.original_filename)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=document.original_filename)


@router.post("/documents/{document_id}/delete")
def documents_delete(
    document_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_documents_access_web),
):
    document = db.get(models.Document, document_id)
    if document:
        path = UPLOAD_ROOT / document.file_path
        db.delete(document)
        db.commit()
        if path.exists():
            path.unlink()
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
        stored_name, original_name = await _save_upload(file, PHOTOS_DIR, ALLOWED_PHOTO_EXT)
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
    path = UPLOAD_ROOT / photo.file_path
    if not path.exists():
        return RedirectResponse(url="/admin/photos", status_code=status.HTTP_303_SEE_OTHER)
    media_type = mimetypes.guess_type(photo.original_filename)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)


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
        path = UPLOAD_ROOT / photo.file_path
        db.delete(photo)
        db.commit()
        if path.exists():
            path.unlink()
    return RedirectResponse(url="/admin/photos", status_code=status.HTTP_303_SEE_OTHER)
