import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from .. import audit, models
from ..database import get_db
from ..deps import require_enseignants_access_web

router = APIRouter(prefix="/admin/enseignants", tags=["admin-enseignants"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def enseignants_list(
    request: Request,
    etablissement_id: int | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_enseignants_access_web),
):
    query = db.query(models.Enseignant).options(joinedload(models.Enseignant.etablissement))
    if etablissement_id:
        query = query.filter(models.Enseignant.etablissement_id == etablissement_id)
    items = query.order_by(models.Enseignant.full_name).all()
    etablissements = db.query(models.Etablissement).order_by(models.Etablissement.nom).all()
    return templates.TemplateResponse(
        request,
        "admin/enseignants_list.html",
        {
            "admin": user,
            "items": items,
            "etablissements": etablissements,
            "selected_etablissement_id": etablissement_id,
            "active": "enseignants",
        },
    )


@router.get("/new")
def enseignants_new_form(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_enseignants_access_web),
):
    etablissements = db.query(models.Etablissement).order_by(models.Etablissement.nom).all()
    return templates.TemplateResponse(
        request,
        "admin/enseignant_form.html",
        {"admin": user, "item": None, "etablissements": etablissements, "active": "enseignants"},
    )


@router.post("/new")
def enseignants_create(
    full_name: str = Form(...),
    etablissement_id: int = Form(...),
    matiere: str = Form(""),
    diplome: str = Form(""),
    telephone: str = Form(""),
    email: str = Form(""),
    date_debut: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_enseignants_access_web),
):
    enseignant = models.Enseignant(
        full_name=full_name,
        etablissement_id=etablissement_id,
        matiere=matiere or None,
        diplome=diplome or None,
        telephone=telephone or None,
        email=email or None,
        date_debut=datetime.date.fromisoformat(date_debut) if date_debut else None,
        notes=notes or None,
    )
    db.add(enseignant)
    db.flush()
    audit.log(db, user, "create", "Enseignant", enseignant.id, f"A ajouté l'enseignant {enseignant.full_name}")
    db.commit()
    return RedirectResponse(url="/admin/enseignants", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{enseignant_id}/edit")
def enseignants_edit_form(
    enseignant_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_enseignants_access_web),
):
    item = db.get(models.Enseignant, enseignant_id)
    etablissements = db.query(models.Etablissement).order_by(models.Etablissement.nom).all()
    return templates.TemplateResponse(
        request,
        "admin/enseignant_form.html",
        {"admin": user, "item": item, "etablissements": etablissements, "active": "enseignants"},
    )


@router.post("/{enseignant_id}/edit")
def enseignants_update(
    enseignant_id: int,
    full_name: str = Form(...),
    etablissement_id: int = Form(...),
    matiere: str = Form(""),
    diplome: str = Form(""),
    telephone: str = Form(""),
    email: str = Form(""),
    date_debut: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_enseignants_access_web),
):
    enseignant = db.get(models.Enseignant, enseignant_id)
    if enseignant:
        enseignant.full_name = full_name
        enseignant.etablissement_id = etablissement_id
        enseignant.matiere = matiere or None
        enseignant.diplome = diplome or None
        enseignant.telephone = telephone or None
        enseignant.email = email or None
        enseignant.date_debut = datetime.date.fromisoformat(date_debut) if date_debut else None
        enseignant.notes = notes or None
        audit.log(db, user, "update", "Enseignant", enseignant.id, f"A modifié l'enseignant {enseignant.full_name}")
        db.commit()
    return RedirectResponse(url="/admin/enseignants", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{enseignant_id}/delete")
def enseignants_delete(
    enseignant_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_enseignants_access_web),
):
    enseignant = db.get(models.Enseignant, enseignant_id)
    if enseignant:
        audit.log(db, user, "delete", "Enseignant", enseignant.id, f"A retiré l'enseignant {enseignant.full_name}")
        db.delete(enseignant)
        db.commit()
    return RedirectResponse(url="/admin/enseignants", status_code=status.HTTP_303_SEE_OTHER)
