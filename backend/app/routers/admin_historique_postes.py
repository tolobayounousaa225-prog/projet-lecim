import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import audit, models
from ..database import get_db
from ..deps import require_gouvernance_access_web

router = APIRouter(prefix="/admin/historique-postes", tags=["admin-historique-postes"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def historique_postes_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_gouvernance_access_web),
):
    items = (
        db.query(models.HistoriquePoste)
        .order_by(models.HistoriquePoste.date_fin.is_not(None), models.HistoriquePoste.date_debut.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/historique_postes_list.html",
        {"admin": user, "items": items, "active": "historique_postes"},
    )


@router.get("/new")
def historique_postes_new_form(
    request: Request,
    user: models.User = Depends(require_gouvernance_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/historique_postes_form.html",
        {"admin": user, "item": None, "active": "historique_postes", "error": None},
    )


@router.post("/new")
def historique_postes_create(
    request: Request,
    poste_label: str = Form(...),
    titulaire_nom: str = Form(...),
    date_debut: str = Form(...),
    date_fin: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_gouvernance_access_web),
):
    try:
        parsed_debut = datetime.date.fromisoformat(date_debut)
        parsed_fin = datetime.date.fromisoformat(date_fin) if date_fin else None
    except ValueError:
        return templates.TemplateResponse(
            request, "admin/historique_postes_form.html",
            {"admin": user, "item": None, "active": "historique_postes", "error": "Date invalide."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    poste = models.HistoriquePoste(
        poste_label=poste_label, titulaire_nom=titulaire_nom, date_debut=parsed_debut,
        date_fin=parsed_fin, notes=notes or None, created_by_id=user.id,
    )
    db.add(poste)
    db.flush()
    audit.log(db, user, "create", "Historique poste BEN", poste.id, f"A ajouté {titulaire_nom} ({poste_label}) à l'historique des postes")
    db.commit()
    return RedirectResponse(url="/admin/historique-postes", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{poste_id}/edit")
def historique_postes_edit_form(
    poste_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_gouvernance_access_web),
):
    item = db.get(models.HistoriquePoste, poste_id)
    if not item:
        return RedirectResponse(url="/admin/historique-postes", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request,
        "admin/historique_postes_form.html",
        {"admin": user, "item": item, "active": "historique_postes", "error": None},
    )


@router.post("/{poste_id}/edit")
def historique_postes_update(
    poste_id: int,
    request: Request,
    poste_label: str = Form(...),
    titulaire_nom: str = Form(...),
    date_debut: str = Form(...),
    date_fin: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_gouvernance_access_web),
):
    item = db.get(models.HistoriquePoste, poste_id)
    if not item:
        return RedirectResponse(url="/admin/historique-postes", status_code=status.HTTP_303_SEE_OTHER)
    try:
        parsed_debut = datetime.date.fromisoformat(date_debut)
        parsed_fin = datetime.date.fromisoformat(date_fin) if date_fin else None
    except ValueError:
        return templates.TemplateResponse(
            request, "admin/historique_postes_form.html",
            {"admin": user, "item": item, "active": "historique_postes", "error": "Date invalide."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    item.poste_label = poste_label
    item.titulaire_nom = titulaire_nom
    item.date_debut = parsed_debut
    item.date_fin = parsed_fin
    item.notes = notes or None
    audit.log(db, user, "update", "Historique poste BEN", item.id, f"A modifié l'entrée de {titulaire_nom} ({poste_label})")
    db.commit()
    return RedirectResponse(url="/admin/historique-postes", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{poste_id}/delete")
def historique_postes_delete(
    poste_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_gouvernance_access_web),
):
    item = db.get(models.HistoriquePoste, poste_id)
    if item:
        audit.log(db, user, "delete", "Historique poste BEN", item.id, f"A supprimé l'entrée de {item.titulaire_nom} ({item.poste_label})")
        db.delete(item)
        db.commit()
    return RedirectResponse(url="/admin/historique-postes", status_code=status.HTTP_303_SEE_OTHER)
