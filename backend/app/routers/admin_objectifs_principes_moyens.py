from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_publications_access_web
from ..models import OPM_CATEGORIES

router = APIRouter(prefix="/admin/objectifs-principes-moyens", tags=["admin-objectifs-principes-moyens"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def opm_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    items = (
        db.query(models.ObjectifPrincipeMoyen)
        .order_by(models.ObjectifPrincipeMoyen.categorie, models.ObjectifPrincipeMoyen.ordre, models.ObjectifPrincipeMoyen.id)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/opm_list.html",
        {"admin": user, "items": items, "categories": OPM_CATEGORIES, "active": "opm"},
    )


@router.get("/new")
def opm_new_form(
    request: Request,
    user: models.User = Depends(require_publications_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/opm_form.html",
        {"admin": user, "item": None, "categories": OPM_CATEGORIES, "active": "opm"},
    )


@router.post("/new")
def opm_create(
    categorie: str = Form(...),
    contenu: str = Form(...),
    ordre: int = Form(0),
    is_published: bool = Form(False),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    item = models.ObjectifPrincipeMoyen(
        categorie=categorie if categorie in OPM_CATEGORIES else "objectif",
        contenu=contenu,
        ordre=ordre,
        is_published=is_published,
    )
    db.add(item)
    db.commit()
    return RedirectResponse(url="/admin/objectifs-principes-moyens", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{item_id}/edit")
def opm_edit_form(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    item = db.get(models.ObjectifPrincipeMoyen, item_id)
    return templates.TemplateResponse(
        request,
        "admin/opm_form.html",
        {"admin": user, "item": item, "categories": OPM_CATEGORIES, "active": "opm"},
    )


@router.post("/{item_id}/edit")
def opm_update(
    item_id: int,
    categorie: str = Form(...),
    contenu: str = Form(...),
    ordre: int = Form(0),
    is_published: bool = Form(False),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    item = db.get(models.ObjectifPrincipeMoyen, item_id)
    if item:
        item.categorie = categorie if categorie in OPM_CATEGORIES else "objectif"
        item.contenu = contenu
        item.ordre = ordre
        item.is_published = is_published
        db.commit()
    return RedirectResponse(url="/admin/objectifs-principes-moyens", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{item_id}/delete")
def opm_delete(
    item_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    item = db.get(models.ObjectifPrincipeMoyen, item_id)
    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse(url="/admin/objectifs-principes-moyens", status_code=status.HTTP_303_SEE_OTHER)
