import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_activities_access_web
from ..models import CALENDRIER_SCOLAIRE_TYPES
from ..reports import current_annee_scolaire

router = APIRouter(prefix="/admin/calendrier-scolaire", tags=["admin-calendrier-scolaire"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def calendrier_scolaire_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_activities_access_web),
):
    items = (
        db.query(models.CalendrierScolaireEntry)
        .order_by(models.CalendrierScolaireEntry.date_debut.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/calendrier_scolaire_list.html",
        {"admin": user, "items": items, "types": CALENDRIER_SCOLAIRE_TYPES, "active": "calendrier_scolaire"},
    )


@router.get("/new")
def calendrier_scolaire_new_form(
    request: Request,
    user: models.User = Depends(require_activities_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/calendrier_scolaire_form.html",
        {
            "admin": user,
            "item": None,
            "types": CALENDRIER_SCOLAIRE_TYPES,
            "default_annee": current_annee_scolaire(),
            "active": "calendrier_scolaire",
        },
    )


@router.post("/new")
def calendrier_scolaire_create(
    titre: str = Form(...),
    type: str = Form("autre"),
    date_debut: str = Form(...),
    date_fin: str = Form(""),
    annee_scolaire: str = Form(...),
    description: str = Form(""),
    is_published: bool = Form(False),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_activities_access_web),
):
    entry = models.CalendrierScolaireEntry(
        titre=titre,
        type=type if type in CALENDRIER_SCOLAIRE_TYPES else "autre",
        date_debut=datetime.date.fromisoformat(date_debut),
        date_fin=datetime.date.fromisoformat(date_fin) if date_fin else None,
        annee_scolaire=annee_scolaire,
        description=description or None,
        is_published=is_published,
        created_by_id=user.id,
    )
    db.add(entry)
    db.commit()
    return RedirectResponse(url="/admin/calendrier-scolaire", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{entry_id}/edit")
def calendrier_scolaire_edit_form(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_activities_access_web),
):
    item = db.get(models.CalendrierScolaireEntry, entry_id)
    if not item:
        return RedirectResponse(url="/admin/calendrier-scolaire", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request,
        "admin/calendrier_scolaire_form.html",
        {"admin": user, "item": item, "types": CALENDRIER_SCOLAIRE_TYPES, "default_annee": item.annee_scolaire, "active": "calendrier_scolaire"},
    )


@router.post("/{entry_id}/edit")
def calendrier_scolaire_update(
    entry_id: int,
    titre: str = Form(...),
    type: str = Form("autre"),
    date_debut: str = Form(...),
    date_fin: str = Form(""),
    annee_scolaire: str = Form(...),
    description: str = Form(""),
    is_published: bool = Form(False),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_activities_access_web),
):
    entry = db.get(models.CalendrierScolaireEntry, entry_id)
    if entry:
        entry.titre = titre
        entry.type = type if type in CALENDRIER_SCOLAIRE_TYPES else "autre"
        entry.date_debut = datetime.date.fromisoformat(date_debut)
        entry.date_fin = datetime.date.fromisoformat(date_fin) if date_fin else None
        entry.annee_scolaire = annee_scolaire
        entry.description = description or None
        entry.is_published = is_published
        db.commit()
    return RedirectResponse(url="/admin/calendrier-scolaire", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{entry_id}/delete")
def calendrier_scolaire_delete(
    entry_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_activities_access_web),
):
    entry = db.get(models.CalendrierScolaireEntry, entry_id)
    if entry:
        db.delete(entry)
        db.commit()
    return RedirectResponse(url="/admin/calendrier-scolaire", status_code=status.HTTP_303_SEE_OTHER)
