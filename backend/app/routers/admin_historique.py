from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models, storage
from ..database import get_db
from ..deps import require_historique_access_web
from .admin_files import ALLOWED_PHOTO_EXT

router = APIRouter(prefix="/admin/historique", tags=["admin-historique"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

HISTORIQUE_DIR = "historique"


@router.get("")
def historique_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_historique_access_web),
):
    items = (
        db.query(models.HistoriquePresident)
        .order_by(models.HistoriquePresident.ordre, models.HistoriquePresident.id)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/historique_list.html",
        {"admin": user, "items": items, "active": "historique"},
    )


@router.get("/new")
def historique_new_form(
    request: Request,
    user: models.User = Depends(require_historique_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/historique_form.html",
        {"admin": user, "item": None, "active": "historique", "error": None},
    )


@router.post("/new")
async def historique_create(
    request: Request,
    full_name: str = Form(...),
    periode: str = Form(""),
    mot: str = Form(""),
    ordre: int = Form(0),
    is_published: bool = Form(False),
    photo: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_historique_access_web),
):
    photo_path = None
    if photo is not None and photo.filename:
        try:
            stored_name, _ = await storage.save_upload(db, photo, HISTORIQUE_DIR, ALLOWED_PHOTO_EXT)
            photo_path = f"historique/{stored_name}"
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "admin/historique_form.html",
                {"admin": user, "item": None, "active": "historique", "error": str(exc)},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    president = models.HistoriquePresident(
        full_name=full_name,
        periode=periode or None,
        mot=mot or None,
        ordre=ordre,
        is_published=is_published,
        photo_path=photo_path,
        uploaded_by_id=user.id,
    )
    db.add(president)
    db.commit()
    return RedirectResponse(url="/admin/historique", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{president_id}/edit")
def historique_edit_form(
    president_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_historique_access_web),
):
    item = db.get(models.HistoriquePresident, president_id)
    return templates.TemplateResponse(
        request,
        "admin/historique_form.html",
        {"admin": user, "item": item, "active": "historique", "error": None},
    )


@router.post("/{president_id}/edit")
async def historique_update(
    president_id: int,
    request: Request,
    full_name: str = Form(...),
    periode: str = Form(""),
    mot: str = Form(""),
    ordre: int = Form(0),
    is_published: bool = Form(False),
    photo: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_historique_access_web),
):
    president = db.get(models.HistoriquePresident, president_id)
    if not president:
        return RedirectResponse(url="/admin/historique", status_code=status.HTTP_303_SEE_OTHER)

    if photo is not None and photo.filename:
        try:
            stored_name, _ = await storage.save_upload(db, photo, HISTORIQUE_DIR, ALLOWED_PHOTO_EXT)
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "admin/historique_form.html",
                {"admin": user, "item": president, "active": "historique", "error": str(exc)},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        storage.delete_stored_file(db, president.photo_path)
        president.photo_path = f"historique/{stored_name}"

    president.full_name = full_name
    president.periode = periode or None
    president.mot = mot or None
    president.ordre = ordre
    president.is_published = is_published
    db.commit()
    return RedirectResponse(url="/admin/historique", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{president_id}/delete")
def historique_delete(
    president_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_historique_access_web),
):
    president = db.get(models.HistoriquePresident, president_id)
    if president:
        storage.delete_stored_file(db, president.photo_path)
        db.delete(president)
        db.commit()
    return RedirectResponse(url="/admin/historique", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{president_id}/toggle")
def historique_toggle(
    president_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_historique_access_web),
):
    president = db.get(models.HistoriquePresident, president_id)
    if president:
        president.is_published = not president.is_published
        db.commit()
    return RedirectResponse(url="/admin/historique", status_code=status.HTTP_303_SEE_OTHER)
