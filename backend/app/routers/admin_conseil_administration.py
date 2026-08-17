from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_gouvernance_access_web
from .admin_files import ALLOWED_PHOTO_EXT, UPLOAD_ROOT, _save_upload

router = APIRouter(prefix="/admin/conseil-administration", tags=["admin-conseil-administration"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

CONSEIL_ADMINISTRATION_DIR = UPLOAD_ROOT / "conseil_administration"


@router.get("")
def conseil_administration_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_gouvernance_access_web),
):
    items = (
        db.query(models.MembreConseilAdministration)
        .order_by(models.MembreConseilAdministration.ordre, models.MembreConseilAdministration.id)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/conseil_administration_list.html",
        {"admin": user, "items": items, "active": "conseil_administration"},
    )


@router.get("/new")
def conseil_administration_new_form(
    request: Request,
    user: models.User = Depends(require_gouvernance_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/conseil_administration_form.html",
        {"admin": user, "item": None, "active": "conseil_administration", "error": None},
    )


@router.post("/new")
async def conseil_administration_create(
    request: Request,
    full_name: str = Form(...),
    role: str = Form(""),
    mot: str = Form(""),
    ordre: int = Form(0),
    is_published: bool = Form(False),
    photo: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_gouvernance_access_web),
):
    photo_path = None
    if photo is not None and photo.filename:
        try:
            stored_name, _ = await _save_upload(photo, CONSEIL_ADMINISTRATION_DIR, ALLOWED_PHOTO_EXT)
            photo_path = f"conseil_administration/{stored_name}"
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "admin/conseil_administration_form.html",
                {"admin": user, "item": None, "active": "conseil_administration", "error": str(exc)},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    membre = models.MembreConseilAdministration(
        full_name=full_name,
        role=role or None,
        mot=mot or None,
        ordre=ordre,
        is_published=is_published,
        photo_path=photo_path,
        uploaded_by_id=user.id,
    )
    db.add(membre)
    db.commit()
    return RedirectResponse(url="/admin/conseil-administration", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{membre_id}/edit")
def conseil_administration_edit_form(
    membre_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_gouvernance_access_web),
):
    item = db.get(models.MembreConseilAdministration, membre_id)
    return templates.TemplateResponse(
        request,
        "admin/conseil_administration_form.html",
        {"admin": user, "item": item, "active": "conseil_administration", "error": None},
    )


@router.post("/{membre_id}/edit")
async def conseil_administration_update(
    membre_id: int,
    request: Request,
    full_name: str = Form(...),
    role: str = Form(""),
    mot: str = Form(""),
    ordre: int = Form(0),
    is_published: bool = Form(False),
    photo: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_gouvernance_access_web),
):
    membre = db.get(models.MembreConseilAdministration, membre_id)
    if not membre:
        return RedirectResponse(url="/admin/conseil-administration", status_code=status.HTTP_303_SEE_OTHER)

    if photo is not None and photo.filename:
        try:
            stored_name, _ = await _save_upload(photo, CONSEIL_ADMINISTRATION_DIR, ALLOWED_PHOTO_EXT)
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "admin/conseil_administration_form.html",
                {"admin": user, "item": membre, "active": "conseil_administration", "error": str(exc)},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        old_path = UPLOAD_ROOT / membre.photo_path if membre.photo_path else None
        membre.photo_path = f"conseil_administration/{stored_name}"
        if old_path and old_path.exists():
            old_path.unlink()

    membre.full_name = full_name
    membre.role = role or None
    membre.mot = mot or None
    membre.ordre = ordre
    membre.is_published = is_published
    db.commit()
    return RedirectResponse(url="/admin/conseil-administration", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{membre_id}/delete")
def conseil_administration_delete(
    membre_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_gouvernance_access_web),
):
    membre = db.get(models.MembreConseilAdministration, membre_id)
    if membre:
        path = UPLOAD_ROOT / membre.photo_path if membre.photo_path else None
        db.delete(membre)
        db.commit()
        if path and path.exists():
            path.unlink()
    return RedirectResponse(url="/admin/conseil-administration", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{membre_id}/toggle")
def conseil_administration_toggle(
    membre_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_gouvernance_access_web),
):
    membre = db.get(models.MembreConseilAdministration, membre_id)
    if membre:
        membre.is_published = not membre.is_published
        db.commit()
    return RedirectResponse(url="/admin/conseil-administration", status_code=status.HTTP_303_SEE_OTHER)
