import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import audit, models
from ..database import get_db
from ..deps import require_visites_access_web

router = APIRouter(prefix="/admin/visites", tags=["admin-visites"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def visites_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_visites_access_web),
):
    items = db.query(models.VisiteEtablissement).order_by(models.VisiteEtablissement.date.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin/visites_list.html",
        {"admin": user, "items": items, "active": "visites"},
    )


@router.get("/new")
def visites_new_form(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_visites_access_web),
):
    etablissements = db.query(models.Etablissement).order_by(models.Etablissement.nom).all()
    return templates.TemplateResponse(
        request,
        "admin/visite_form.html",
        {"admin": user, "item": None, "etablissements": etablissements, "active": "visites"},
    )


@router.post("/new")
def visites_create(
    etablissement_id: int = Form(...),
    date: str = Form(...),
    constat: str = Form(...),
    suites_a_donner: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_visites_access_web),
):
    visite = models.VisiteEtablissement(
        etablissement_id=etablissement_id,
        date=datetime.date.fromisoformat(date),
        constat=constat,
        suites_a_donner=suites_a_donner or None,
        created_by_id=user.id,
    )
    db.add(visite)
    db.flush()
    audit.log(db, user, "create", "Visite établissement", visite.id, f"A enregistré une visite (établissement #{etablissement_id})")
    db.commit()
    return RedirectResponse(url="/admin/visites", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{visite_id}/edit")
def visites_edit_form(
    visite_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_visites_access_web),
):
    item = db.get(models.VisiteEtablissement, visite_id)
    if not item:
        return RedirectResponse(url="/admin/visites", status_code=status.HTTP_303_SEE_OTHER)
    etablissements = db.query(models.Etablissement).order_by(models.Etablissement.nom).all()
    return templates.TemplateResponse(
        request,
        "admin/visite_form.html",
        {"admin": user, "item": item, "etablissements": etablissements, "active": "visites"},
    )


@router.post("/{visite_id}/edit")
def visites_update(
    visite_id: int,
    etablissement_id: int = Form(...),
    date: str = Form(...),
    constat: str = Form(...),
    suites_a_donner: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_visites_access_web),
):
    item = db.get(models.VisiteEtablissement, visite_id)
    if item:
        item.etablissement_id = etablissement_id
        item.date = datetime.date.fromisoformat(date)
        item.constat = constat
        item.suites_a_donner = suites_a_donner or None
        audit.log(db, user, "update", "Visite établissement", item.id, "A modifié une visite d'établissement")
        db.commit()
    return RedirectResponse(url="/admin/visites", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{visite_id}/delete")
def visites_delete(
    visite_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_visites_access_web),
):
    item = db.get(models.VisiteEtablissement, visite_id)
    if item:
        audit.log(db, user, "delete", "Visite établissement", item.id, "A supprimé une visite d'établissement")
        db.delete(item)
        db.commit()
    return RedirectResponse(url="/admin/visites", status_code=status.HTTP_303_SEE_OTHER)
