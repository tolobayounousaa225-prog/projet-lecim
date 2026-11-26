"""Gestion des documents reserves aux membres (comptes-rendus, circulaires,
supports de formation), accessibles depuis l'Espace Membre public apres
verification carte + date de naissance (voir routers/espace_membre.py)."""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models, storage
from ..database import get_db
from ..deps import require_publications_access_web
from .admin_files import ALLOWED_DOCUMENT_EXT

router = APIRouter(prefix="/admin/ressources-membres", tags=["admin-ressources-membres"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

RESSOURCES_MEMBRES_DIR = "ressources_membres"


@router.get("")
def ressources_membres_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    items = (
        db.query(models.RessourceMembre)
        .order_by(models.RessourceMembre.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/ressources_membres_list.html",
        {"admin": user, "items": items, "active": "ressources_membres"},
    )


@router.get("/new")
def ressources_membres_new_form(
    request: Request,
    user: models.User = Depends(require_publications_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/ressource_membre_form.html",
        {"admin": user, "item": None, "active": "ressources_membres", "error": None},
    )


@router.post("/new")
async def ressources_membres_create(
    request: Request,
    titre: str = Form(...),
    description: str = Form(""),
    is_published: bool = Form(False),
    file: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    if file is None or not file.filename:
        return templates.TemplateResponse(
            request,
            "admin/ressource_membre_form.html",
            {"admin": user, "item": None, "active": "ressources_membres", "error": "Un fichier est requis."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        stored_name, original_name = await storage.save_upload(db, file, RESSOURCES_MEMBRES_DIR, ALLOWED_DOCUMENT_EXT)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "admin/ressource_membre_form.html",
            {"admin": user, "item": None, "active": "ressources_membres", "error": str(exc)},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    ressource = models.RessourceMembre(
        titre=titre,
        description=description or None,
        file_path=f"{RESSOURCES_MEMBRES_DIR}/{stored_name}",
        original_filename=original_name,
        is_published=is_published,
        uploaded_by_id=user.id,
    )
    db.add(ressource)
    db.commit()
    return RedirectResponse(url="/admin/ressources-membres", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{ressource_id}/edit")
def ressources_membres_edit_form(
    ressource_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    item = db.get(models.RessourceMembre, ressource_id)
    return templates.TemplateResponse(
        request,
        "admin/ressource_membre_form.html",
        {"admin": user, "item": item, "active": "ressources_membres", "error": None},
    )


@router.post("/{ressource_id}/edit")
async def ressources_membres_update(
    ressource_id: int,
    request: Request,
    titre: str = Form(...),
    description: str = Form(""),
    is_published: bool = Form(False),
    file: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    ressource = db.get(models.RessourceMembre, ressource_id)
    if not ressource:
        return RedirectResponse(url="/admin/ressources-membres", status_code=status.HTTP_303_SEE_OTHER)

    if file is not None and file.filename:
        try:
            stored_name, original_name = await storage.save_upload(
                db, file, RESSOURCES_MEMBRES_DIR, ALLOWED_DOCUMENT_EXT
            )
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "admin/ressource_membre_form.html",
                {"admin": user, "item": ressource, "active": "ressources_membres", "error": str(exc)},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        storage.delete_stored_file(db, ressource.file_path)
        ressource.file_path = f"{RESSOURCES_MEMBRES_DIR}/{stored_name}"
        ressource.original_filename = original_name

    ressource.titre = titre
    ressource.description = description or None
    ressource.is_published = is_published
    db.commit()
    return RedirectResponse(url="/admin/ressources-membres", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{ressource_id}/delete")
def ressources_membres_delete(
    ressource_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    ressource = db.get(models.RessourceMembre, ressource_id)
    if ressource:
        storage.delete_stored_file(db, ressource.file_path)
        db.delete(ressource)
        db.commit()
    return RedirectResponse(url="/admin/ressources-membres", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{ressource_id}/toggle")
def ressources_membres_toggle(
    ressource_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    ressource = db.get(models.RessourceMembre, ressource_id)
    if ressource:
        ressource.is_published = not ressource.is_published
        db.commit()
    return RedirectResponse(url="/admin/ressources-membres", status_code=status.HTTP_303_SEE_OTHER)
