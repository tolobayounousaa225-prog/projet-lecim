from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models, storage
from ..database import get_db
from ..deps import require_fondateurs_access_web
from .admin_files import ALLOWED_PHOTO_EXT

router = APIRouter(prefix="/admin/fondateurs", tags=["admin-fondateurs"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

FONDATEURS_DIR = "fondateurs"


@router.get("")
def fondateurs_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_fondateurs_access_web),
):
    items = (
        db.query(models.MembreFondateur)
        .order_by(models.MembreFondateur.ordre, models.MembreFondateur.id)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/fondateurs_list.html",
        {"admin": user, "items": items, "active": "fondateurs"},
    )


@router.get("/new")
def fondateurs_new_form(
    request: Request,
    user: models.User = Depends(require_fondateurs_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/fondateur_form.html",
        {"admin": user, "item": None, "active": "fondateurs", "error": None},
    )


@router.post("/new")
async def fondateurs_create(
    request: Request,
    full_name: str = Form(...),
    role: str = Form(""),
    mot: str = Form(""),
    ordre: int = Form(0),
    is_published: bool = Form(False),
    photo: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_fondateurs_access_web),
):
    photo_path = None
    if photo is not None and photo.filename:
        try:
            stored_name, _ = await storage.save_upload(db, photo, FONDATEURS_DIR, ALLOWED_PHOTO_EXT)
            photo_path = f"fondateurs/{stored_name}"
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "admin/fondateur_form.html",
                {"admin": user, "item": None, "active": "fondateurs", "error": str(exc)},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    fondateur = models.MembreFondateur(
        full_name=full_name,
        role=role or None,
        mot=mot or None,
        ordre=ordre,
        is_published=is_published,
        photo_path=photo_path,
        uploaded_by_id=user.id,
    )
    db.add(fondateur)
    db.commit()
    return RedirectResponse(url="/admin/fondateurs", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{fondateur_id}/edit")
def fondateurs_edit_form(
    fondateur_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_fondateurs_access_web),
):
    item = db.get(models.MembreFondateur, fondateur_id)
    return templates.TemplateResponse(
        request,
        "admin/fondateur_form.html",
        {"admin": user, "item": item, "active": "fondateurs", "error": None},
    )


@router.post("/{fondateur_id}/edit")
async def fondateurs_update(
    fondateur_id: int,
    request: Request,
    full_name: str = Form(...),
    role: str = Form(""),
    mot: str = Form(""),
    ordre: int = Form(0),
    is_published: bool = Form(False),
    photo: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_fondateurs_access_web),
):
    fondateur = db.get(models.MembreFondateur, fondateur_id)
    if not fondateur:
        return RedirectResponse(url="/admin/fondateurs", status_code=status.HTTP_303_SEE_OTHER)

    if photo is not None and photo.filename:
        try:
            stored_name, _ = await storage.save_upload(db, photo, FONDATEURS_DIR, ALLOWED_PHOTO_EXT)
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "admin/fondateur_form.html",
                {"admin": user, "item": fondateur, "active": "fondateurs", "error": str(exc)},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        storage.delete_stored_file(db, fondateur.photo_path)
        fondateur.photo_path = f"fondateurs/{stored_name}"

    fondateur.full_name = full_name
    fondateur.role = role or None
    fondateur.mot = mot or None
    fondateur.ordre = ordre
    fondateur.is_published = is_published
    db.commit()
    return RedirectResponse(url="/admin/fondateurs", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{fondateur_id}/delete")
def fondateurs_delete(
    fondateur_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_fondateurs_access_web),
):
    fondateur = db.get(models.MembreFondateur, fondateur_id)
    if fondateur:
        storage.delete_stored_file(db, fondateur.photo_path)
        db.delete(fondateur)
        db.commit()
    return RedirectResponse(url="/admin/fondateurs", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{fondateur_id}/toggle")
def fondateurs_toggle(
    fondateur_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_fondateurs_access_web),
):
    fondateur = db.get(models.MembreFondateur, fondateur_id)
    if fondateur:
        fondateur.is_published = not fondateur.is_published
        db.commit()
    return RedirectResponse(url="/admin/fondateurs", status_code=status.HTTP_303_SEE_OTHER)
