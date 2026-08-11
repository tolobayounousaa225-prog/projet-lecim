import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_affaires_sociales_access_web
from ..models import DEMANDE_ASSISTANCE_STATUTS

router = APIRouter(prefix="/admin/social", tags=["admin-social"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def social_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_affaires_sociales_access_web),
):
    items = db.query(models.DemandeAssistance).order_by(models.DemandeAssistance.date_soumission.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin/social_list.html",
        {"admin": user, "items": items, "statuts": DEMANDE_ASSISTANCE_STATUTS, "active": "social"},
    )


@router.get("/new")
def social_new_form(
    request: Request,
    user: models.User = Depends(require_affaires_sociales_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/social_form.html",
        {"admin": user, "active": "social"},
    )


@router.post("/new")
def social_create(
    nom_beneficiaire: str = Form(...),
    structure: str = Form(""),
    nature_besoin: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_affaires_sociales_access_web),
):
    demande = models.DemandeAssistance(
        nom_beneficiaire=nom_beneficiaire,
        structure=structure or None,
        nature_besoin=nature_besoin,
        description=description or None,
        recorded_by_id=user.id,
    )
    db.add(demande)
    db.commit()
    return RedirectResponse(url="/admin/social", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{demande_id}")
def social_detail(
    demande_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_affaires_sociales_access_web),
):
    demande = db.get(models.DemandeAssistance, demande_id)
    if not demande:
        return RedirectResponse(url="/admin/social", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request,
        "admin/social_detail.html",
        {"admin": user, "demande": demande, "statuts": DEMANDE_ASSISTANCE_STATUTS, "active": "social"},
    )


@router.post("/{demande_id}/statut")
def social_update_statut(
    demande_id: int,
    statut: str = Form(...),
    notes_suivi: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_affaires_sociales_access_web),
):
    demande = db.get(models.DemandeAssistance, demande_id)
    if demande and statut in DEMANDE_ASSISTANCE_STATUTS:
        demande.statut = statut
        demande.notes_suivi = notes_suivi or None
        if statut in {"traitee", "rejetee"}:
            demande.date_traitement = datetime.datetime.utcnow()
        db.commit()
    return RedirectResponse(url=f"/admin/social/{demande_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{demande_id}/delete")
def social_delete(
    demande_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_affaires_sociales_access_web),
):
    demande = db.get(models.DemandeAssistance, demande_id)
    if demande:
        db.delete(demande)
        db.commit()
    return RedirectResponse(url="/admin/social", status_code=status.HTTP_303_SEE_OTHER)
