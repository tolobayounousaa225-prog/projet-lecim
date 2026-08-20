from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models, storage
from ..database import get_db
from ..deps import require_publications_access_web
from .admin_files import ALLOWED_PHOTO_EXT

router = APIRouter(prefix="/admin/temoignages", tags=["admin-temoignages"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

TEMOIGNAGES_DIR = "temoignages"


@router.get("")
def temoignages_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    items = (
        db.query(models.Temoignage)
        .order_by(models.Temoignage.ordre, models.Temoignage.id)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/temoignages_list.html",
        {"admin": user, "items": items, "active": "temoignages"},
    )


@router.get("/new")
def temoignages_new_form(
    request: Request,
    user: models.User = Depends(require_publications_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/temoignage_form.html",
        {"admin": user, "item": None, "active": "temoignages", "error": None},
    )


@router.post("/new")
async def temoignages_create(
    request: Request,
    auteur_nom: str = Form(...),
    auteur_role: str = Form(""),
    texte: str = Form(...),
    ordre: int = Form(0),
    is_published: bool = Form(False),
    photo: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    photo_path = None
    if photo is not None and photo.filename:
        try:
            stored_name, _ = await storage.save_upload(db, photo, TEMOIGNAGES_DIR, ALLOWED_PHOTO_EXT)
            photo_path = f"temoignages/{stored_name}"
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "admin/temoignage_form.html",
                {"admin": user, "item": None, "active": "temoignages", "error": str(exc)},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    temoignage = models.Temoignage(
        auteur_nom=auteur_nom,
        auteur_role=auteur_role or None,
        texte=texte,
        ordre=ordre,
        is_published=is_published,
        photo_path=photo_path,
        uploaded_by_id=user.id,
    )
    db.add(temoignage)
    db.commit()
    return RedirectResponse(url="/admin/temoignages", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{temoignage_id}/edit")
def temoignages_edit_form(
    temoignage_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    item = db.get(models.Temoignage, temoignage_id)
    return templates.TemplateResponse(
        request,
        "admin/temoignage_form.html",
        {"admin": user, "item": item, "active": "temoignages", "error": None},
    )


@router.post("/{temoignage_id}/edit")
async def temoignages_update(
    temoignage_id: int,
    request: Request,
    auteur_nom: str = Form(...),
    auteur_role: str = Form(""),
    texte: str = Form(...),
    ordre: int = Form(0),
    is_published: bool = Form(False),
    photo: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    temoignage = db.get(models.Temoignage, temoignage_id)
    if not temoignage:
        return RedirectResponse(url="/admin/temoignages", status_code=status.HTTP_303_SEE_OTHER)

    if photo is not None and photo.filename:
        try:
            stored_name, _ = await storage.save_upload(db, photo, TEMOIGNAGES_DIR, ALLOWED_PHOTO_EXT)
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "admin/temoignage_form.html",
                {"admin": user, "item": temoignage, "active": "temoignages", "error": str(exc)},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        storage.delete_stored_file(db, temoignage.photo_path)
        temoignage.photo_path = f"temoignages/{stored_name}"

    temoignage.auteur_nom = auteur_nom
    temoignage.auteur_role = auteur_role or None
    temoignage.texte = texte
    temoignage.ordre = ordre
    temoignage.is_published = is_published
    db.commit()
    return RedirectResponse(url="/admin/temoignages", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{temoignage_id}/delete")
def temoignages_delete(
    temoignage_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    temoignage = db.get(models.Temoignage, temoignage_id)
    if temoignage:
        storage.delete_stored_file(db, temoignage.photo_path)
        db.delete(temoignage)
        db.commit()
    return RedirectResponse(url="/admin/temoignages", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{temoignage_id}/toggle")
def temoignages_toggle(
    temoignage_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    temoignage = db.get(models.Temoignage, temoignage_id)
    if temoignage:
        temoignage.is_published = not temoignage.is_published
        db.commit()
    return RedirectResponse(url="/admin/temoignages", status_code=status.HTTP_303_SEE_OTHER)
