import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_projets_patrimoine_access_web
from ..models import PATRIMOINE_CATEGORIES, PATRIMOINE_ETATS, PROJET_STATUTS

router = APIRouter(prefix="/admin", tags=["admin-projets"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def _date_or_none(value: str) -> datetime.date | None:
    return datetime.date.fromisoformat(value) if value else None


def _int_or_none(value: str) -> int | None:
    return int(value) if value else None


# ---------- Projets ----------

@router.get("/projets")
def projets_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_projets_patrimoine_access_web),
):
    items = db.query(models.Projet).order_by(models.Projet.created_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin/projets_list.html",
        {"admin": user, "items": items, "statuts": PROJET_STATUTS, "active": "projets"},
    )


@router.get("/projets/new")
def projets_new_form(
    request: Request,
    user: models.User = Depends(require_projets_patrimoine_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/projet_form.html",
        {"admin": user, "item": None, "statuts": PROJET_STATUTS, "active": "projets"},
    )


@router.post("/projets/new")
def projets_create(
    titre: str = Form(...),
    description: str = Form(""),
    statut: str = Form("planifie"),
    responsable: str = Form(""),
    date_debut: str = Form(""),
    date_fin_prevue: str = Form(""),
    budget_estime: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_projets_patrimoine_access_web),
):
    projet = models.Projet(
        titre=titre,
        description=description or None,
        statut=statut if statut in PROJET_STATUTS else "planifie",
        responsable=responsable or None,
        date_debut=_date_or_none(date_debut),
        date_fin_prevue=_date_or_none(date_fin_prevue),
        budget_estime=_int_or_none(budget_estime),
        created_by_id=user.id,
    )
    db.add(projet)
    db.commit()
    return RedirectResponse(url="/admin/projets", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/projets/{projet_id}/edit")
def projets_edit_form(
    projet_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_projets_patrimoine_access_web),
):
    item = db.get(models.Projet, projet_id)
    return templates.TemplateResponse(
        request,
        "admin/projet_form.html",
        {"admin": user, "item": item, "statuts": PROJET_STATUTS, "active": "projets"},
    )


@router.post("/projets/{projet_id}/edit")
def projets_update(
    projet_id: int,
    titre: str = Form(...),
    description: str = Form(""),
    statut: str = Form("planifie"),
    responsable: str = Form(""),
    date_debut: str = Form(""),
    date_fin_prevue: str = Form(""),
    budget_estime: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_projets_patrimoine_access_web),
):
    projet = db.get(models.Projet, projet_id)
    if projet:
        projet.titre = titre
        projet.description = description or None
        projet.statut = statut if statut in PROJET_STATUTS else "planifie"
        projet.responsable = responsable or None
        projet.date_debut = _date_or_none(date_debut)
        projet.date_fin_prevue = _date_or_none(date_fin_prevue)
        projet.budget_estime = _int_or_none(budget_estime)
        db.commit()
    return RedirectResponse(url="/admin/projets", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/projets/{projet_id}/delete")
def projets_delete(
    projet_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_projets_patrimoine_access_web),
):
    projet = db.get(models.Projet, projet_id)
    if projet:
        db.delete(projet)
        db.commit()
    return RedirectResponse(url="/admin/projets", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Patrimoine / équipement ----------

@router.get("/patrimoine")
def patrimoine_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_projets_patrimoine_access_web),
):
    items = db.query(models.Patrimoine).order_by(models.Patrimoine.designation).all()
    return templates.TemplateResponse(
        request,
        "admin/patrimoine_list.html",
        {
            "admin": user,
            "items": items,
            "categories": PATRIMOINE_CATEGORIES,
            "etats": PATRIMOINE_ETATS,
            "active": "patrimoine",
        },
    )


@router.get("/patrimoine/new")
def patrimoine_new_form(
    request: Request,
    user: models.User = Depends(require_projets_patrimoine_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/patrimoine_form.html",
        {
            "admin": user,
            "item": None,
            "categories": PATRIMOINE_CATEGORIES,
            "etats": PATRIMOINE_ETATS,
            "active": "patrimoine",
        },
    )


@router.post("/patrimoine/new")
def patrimoine_create(
    designation: str = Form(...),
    categorie: str = Form("autre"),
    quantite: str = Form("1"),
    etat: str = Form("bon"),
    localisation: str = Form(""),
    date_acquisition: str = Form(""),
    valeur_estimee: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_projets_patrimoine_access_web),
):
    bien = models.Patrimoine(
        designation=designation,
        categorie=categorie if categorie in PATRIMOINE_CATEGORIES else "autre",
        quantite=_int_or_none(quantite) or 1,
        etat=etat if etat in PATRIMOINE_ETATS else "bon",
        localisation=localisation or None,
        date_acquisition=_date_or_none(date_acquisition),
        valeur_estimee=_int_or_none(valeur_estimee),
        notes=notes or None,
        created_by_id=user.id,
    )
    db.add(bien)
    db.commit()
    return RedirectResponse(url="/admin/patrimoine", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/patrimoine/{bien_id}/edit")
def patrimoine_edit_form(
    bien_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_projets_patrimoine_access_web),
):
    item = db.get(models.Patrimoine, bien_id)
    return templates.TemplateResponse(
        request,
        "admin/patrimoine_form.html",
        {
            "admin": user,
            "item": item,
            "categories": PATRIMOINE_CATEGORIES,
            "etats": PATRIMOINE_ETATS,
            "active": "patrimoine",
        },
    )


@router.post("/patrimoine/{bien_id}/edit")
def patrimoine_update(
    bien_id: int,
    designation: str = Form(...),
    categorie: str = Form("autre"),
    quantite: str = Form("1"),
    etat: str = Form("bon"),
    localisation: str = Form(""),
    date_acquisition: str = Form(""),
    valeur_estimee: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_projets_patrimoine_access_web),
):
    bien = db.get(models.Patrimoine, bien_id)
    if bien:
        bien.designation = designation
        bien.categorie = categorie if categorie in PATRIMOINE_CATEGORIES else "autre"
        bien.quantite = _int_or_none(quantite) or 1
        bien.etat = etat if etat in PATRIMOINE_ETATS else "bon"
        bien.localisation = localisation or None
        bien.date_acquisition = _date_or_none(date_acquisition)
        bien.valeur_estimee = _int_or_none(valeur_estimee)
        bien.notes = notes or None
        db.commit()
    return RedirectResponse(url="/admin/patrimoine", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/patrimoine/{bien_id}/delete")
def patrimoine_delete(
    bien_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_projets_patrimoine_access_web),
):
    bien = db.get(models.Patrimoine, bien_id)
    if bien:
        db.delete(bien)
        db.commit()
    return RedirectResponse(url="/admin/patrimoine", status_code=status.HTTP_303_SEE_OTHER)
