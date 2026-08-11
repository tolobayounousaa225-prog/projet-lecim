from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_gouvernance_access_web
from .admin_files import ALLOWED_PHOTO_EXT, UPLOAD_ROOT, _save_upload

router = APIRouter(prefix="/admin/gouvernance", tags=["admin-gouvernance"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

GOUVERNANCE_DIR = UPLOAD_ROOT / "gouvernance"


@router.get("")
def gouvernance_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_gouvernance_access_web),
):
    items = (
        db.query(models.GouvernanceMembre)
        .order_by(models.GouvernanceMembre.ordre, models.GouvernanceMembre.id)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/gouvernance_list.html",
        {"admin": user, "items": items, "active": "gouvernance"},
    )


@router.get("/new")
def gouvernance_new_form(
    request: Request,
    user: models.User = Depends(require_gouvernance_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/gouvernance_form.html",
        {"admin": user, "item": None, "active": "gouvernance", "error": None},
    )


async def _handle_photo(
    request: Request,
    photo: UploadFile | None,
    user: models.User,
    item: models.GouvernanceMembre | None,
):
    """Sauvegarde une photo uploadée. Retourne (chemin_relatif, réponse_erreur_ou_None)."""
    if photo is None or not photo.filename:
        return None, None
    try:
        stored_name, _ = await _save_upload(photo, GOUVERNANCE_DIR, ALLOWED_PHOTO_EXT)
        return f"gouvernance/{stored_name}", None
    except ValueError as exc:
        error_response = templates.TemplateResponse(
            request,
            "admin/gouvernance_form.html",
            {"admin": user, "item": item, "active": "gouvernance", "error": str(exc)},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
        return None, error_response


@router.post("/new")
async def gouvernance_create(
    request: Request,
    poste_title: str = Form(...),
    poste_subtitle: str = Form(""),
    titulaire_nom: str = Form(""),
    adjoint_nom: str = Form(""),
    ordre: int = Form(0),
    is_published: bool = Form(False),
    titulaire_photo: UploadFile | None = None,
    adjoint_photo: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_gouvernance_access_web),
):
    titulaire_photo_path, error = await _handle_photo(request, titulaire_photo, user, None)
    if error:
        return error
    adjoint_photo_path, error = await _handle_photo(request, adjoint_photo, user, None)
    if error:
        return error

    membre = models.GouvernanceMembre(
        poste_title=poste_title,
        poste_subtitle=poste_subtitle or None,
        titulaire_nom=titulaire_nom or None,
        titulaire_photo_path=titulaire_photo_path,
        adjoint_nom=adjoint_nom or None,
        adjoint_photo_path=adjoint_photo_path,
        ordre=ordre,
        is_published=is_published,
        uploaded_by_id=user.id,
    )
    db.add(membre)
    db.commit()
    return RedirectResponse(url="/admin/gouvernance", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{membre_id}/edit")
def gouvernance_edit_form(
    membre_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_gouvernance_access_web),
):
    item = db.get(models.GouvernanceMembre, membre_id)
    return templates.TemplateResponse(
        request,
        "admin/gouvernance_form.html",
        {"admin": user, "item": item, "active": "gouvernance", "error": None},
    )


@router.post("/{membre_id}/edit")
async def gouvernance_update(
    membre_id: int,
    request: Request,
    poste_title: str = Form(...),
    poste_subtitle: str = Form(""),
    titulaire_nom: str = Form(""),
    adjoint_nom: str = Form(""),
    ordre: int = Form(0),
    is_published: bool = Form(False),
    titulaire_photo: UploadFile | None = None,
    adjoint_photo: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_gouvernance_access_web),
):
    membre = db.get(models.GouvernanceMembre, membre_id)
    if not membre:
        return RedirectResponse(url="/admin/gouvernance", status_code=status.HTTP_303_SEE_OTHER)

    titulaire_photo_path, error = await _handle_photo(request, titulaire_photo, user, membre)
    if error:
        return error
    adjoint_photo_path, error = await _handle_photo(request, adjoint_photo, user, membre)
    if error:
        return error

    if titulaire_photo_path:
        old_path = UPLOAD_ROOT / membre.titulaire_photo_path if membre.titulaire_photo_path else None
        membre.titulaire_photo_path = titulaire_photo_path
        if old_path and old_path.exists():
            old_path.unlink()
    if adjoint_photo_path:
        old_path = UPLOAD_ROOT / membre.adjoint_photo_path if membre.adjoint_photo_path else None
        membre.adjoint_photo_path = adjoint_photo_path
        if old_path and old_path.exists():
            old_path.unlink()

    membre.poste_title = poste_title
    membre.poste_subtitle = poste_subtitle or None
    membre.titulaire_nom = titulaire_nom or None
    membre.adjoint_nom = adjoint_nom or None
    membre.ordre = ordre
    membre.is_published = is_published
    db.commit()
    return RedirectResponse(url="/admin/gouvernance", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{membre_id}/delete")
def gouvernance_delete(
    membre_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_gouvernance_access_web),
):
    membre = db.get(models.GouvernanceMembre, membre_id)
    if membre:
        paths = [
            UPLOAD_ROOT / membre.titulaire_photo_path if membre.titulaire_photo_path else None,
            UPLOAD_ROOT / membre.adjoint_photo_path if membre.adjoint_photo_path else None,
        ]
        db.delete(membre)
        db.commit()
        for path in paths:
            if path and path.exists():
                path.unlink()
    return RedirectResponse(url="/admin/gouvernance", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{membre_id}/toggle")
def gouvernance_toggle(
    membre_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_gouvernance_access_web),
):
    membre = db.get(models.GouvernanceMembre, membre_id)
    if membre:
        membre.is_published = not membre.is_published
        db.commit()
    return RedirectResponse(url="/admin/gouvernance", status_code=status.HTTP_303_SEE_OTHER)
