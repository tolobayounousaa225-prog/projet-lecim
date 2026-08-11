from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_etablissement_login_web
from ..finances_constants import cotisation_rule
from ..reports import current_annee_scolaire

router = APIRouter(tags=["etablissement-portal"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/etablissement/login")
def etablissement_login_page(request: Request):
    return templates.TemplateResponse(request, "etablissement_login.html", {"error": None})


@router.get("/etablissement/logout")
def etablissement_logout():
    response = RedirectResponse(url="/etablissement/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response


@router.get("/etablissement")
def etablissement_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etablissement_login_web),
):
    etablissement = user.etablissement
    annee = current_annee_scolaire()
    cotisation = (
        db.query(models.Cotisation)
        .filter(models.Cotisation.etablissement_id == etablissement.id, models.Cotisation.annee_scolaire == annee)
        .first()
    )
    counts = {
        "resultats": db.query(models.ResultatExamen)
        .filter(models.ResultatExamen.etablissement_id == etablissement.id, models.ResultatExamen.is_published.is_(True))
        .count(),
        "enseignants": db.query(models.Enseignant).filter(models.Enseignant.etablissement_id == etablissement.id).count(),
        "demandes_ouvertes": db.query(models.DemandeEtablissement)
        .filter(models.DemandeEtablissement.etablissement_id == etablissement.id, models.DemandeEtablissement.statut == "nouvelle")
        .count(),
    }
    return templates.TemplateResponse(
        request,
        "etablissement/dashboard.html",
        {
            "user": user,
            "etablissement": etablissement,
            "annee": annee,
            "cotisation": cotisation,
            "counts": counts,
            "active": "dashboard",
        },
    )


@router.get("/etablissement/cotisation")
def etablissement_cotisation(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etablissement_login_web),
):
    etablissement = user.etablissement
    cotisations = (
        db.query(models.Cotisation)
        .filter(models.Cotisation.etablissement_id == etablissement.id)
        .order_by(models.Cotisation.annee_scolaire.desc())
        .all()
    )
    adhesion = db.query(models.Adhesion).filter(models.Adhesion.etablissement_id == etablissement.id).first()
    rule = cotisation_rule(etablissement.statut)
    return templates.TemplateResponse(
        request,
        "etablissement/cotisation.html",
        {
            "user": user,
            "etablissement": etablissement,
            "cotisations": cotisations,
            "adhesion": adhesion,
            "rule": rule,
            "active": "cotisation",
        },
    )


@router.get("/etablissement/resultats")
def etablissement_resultats(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etablissement_login_web),
):
    etablissement = user.etablissement
    items = (
        db.query(models.ResultatExamen)
        .filter(models.ResultatExamen.etablissement_id == etablissement.id)
        .order_by(models.ResultatExamen.annee_scolaire.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "etablissement/resultats.html",
        {"user": user, "etablissement": etablissement, "items": items, "active": "resultats"},
    )


@router.get("/etablissement/enseignants")
def etablissement_enseignants(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etablissement_login_web),
):
    etablissement = user.etablissement
    items = (
        db.query(models.Enseignant)
        .filter(models.Enseignant.etablissement_id == etablissement.id)
        .order_by(models.Enseignant.full_name)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "etablissement/enseignants.html",
        {"user": user, "etablissement": etablissement, "items": items, "active": "enseignants"},
    )


@router.get("/etablissement/demandes")
def etablissement_demandes(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etablissement_login_web),
):
    etablissement = user.etablissement
    items = (
        db.query(models.DemandeEtablissement)
        .filter(models.DemandeEtablissement.etablissement_id == etablissement.id)
        .order_by(models.DemandeEtablissement.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "etablissement/demandes.html",
        {"user": user, "etablissement": etablissement, "items": items, "active": "demandes"},
    )


@router.post("/etablissement/demandes/new")
def etablissement_demandes_create(
    objet: str = Form(...),
    message: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etablissement_login_web),
):
    demande = models.DemandeEtablissement(
        etablissement_id=user.etablissement_id,
        objet=objet,
        message=message,
    )
    db.add(demande)
    db.commit()
    return RedirectResponse(url="/etablissement/demandes", status_code=status.HTTP_303_SEE_OTHER)
