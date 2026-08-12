from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import audit, models
from ..database import get_db
from ..deps import require_effectifs_access_web
from ..reports import current_annee_scolaire

router = APIRouter(prefix="/admin/effectifs", tags=["admin-effectifs"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def effectifs_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_effectifs_access_web),
):
    items = (
        db.query(models.Effectif)
        .order_by(models.Effectif.annee_scolaire.desc(), models.Effectif.id.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/effectifs_list.html",
        {"admin": user, "items": items, "active": "effectifs"},
    )


@router.get("/new")
def effectifs_new_form(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_effectifs_access_web),
):
    etablissements = db.query(models.Etablissement).order_by(models.Etablissement.nom).all()
    return templates.TemplateResponse(
        request,
        "admin/effectif_form.html",
        {
            "admin": user,
            "item": None,
            "etablissements": etablissements,
            "annee_par_defaut": current_annee_scolaire(),
            "active": "effectifs",
        },
    )


@router.post("/new")
def effectifs_create(
    etablissement_id: int = Form(...),
    annee_scolaire: str = Form(...),
    niveau: str = Form(...),
    nombre_garcons: int = Form(0),
    nombre_filles: int = Form(0),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_effectifs_access_web),
):
    effectif = models.Effectif(
        etablissement_id=etablissement_id,
        annee_scolaire=annee_scolaire,
        niveau=niveau,
        nombre_garcons=nombre_garcons,
        nombre_filles=nombre_filles,
        recorded_by_id=user.id,
    )
    db.add(effectif)
    db.flush()
    audit.log(
        db, user, "create", "Effectif", effectif.id,
        f"A saisi l'effectif {effectif.niveau_label} {effectif.annee_scolaire} de {effectif.etablissement.nom}",
    )
    db.commit()
    return RedirectResponse(url="/admin/effectifs", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{effectif_id}/edit")
def effectifs_edit_form(
    effectif_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_effectifs_access_web),
):
    item = db.get(models.Effectif, effectif_id)
    etablissements = db.query(models.Etablissement).order_by(models.Etablissement.nom).all()
    return templates.TemplateResponse(
        request,
        "admin/effectif_form.html",
        {"admin": user, "item": item, "etablissements": etablissements, "active": "effectifs"},
    )


@router.post("/{effectif_id}/edit")
def effectifs_update(
    effectif_id: int,
    etablissement_id: int = Form(...),
    annee_scolaire: str = Form(...),
    niveau: str = Form(...),
    nombre_garcons: int = Form(0),
    nombre_filles: int = Form(0),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_effectifs_access_web),
):
    effectif = db.get(models.Effectif, effectif_id)
    if effectif:
        effectif.etablissement_id = etablissement_id
        effectif.annee_scolaire = annee_scolaire
        effectif.niveau = niveau
        effectif.nombre_garcons = nombre_garcons
        effectif.nombre_filles = nombre_filles
        audit.log(
            db, user, "update", "Effectif", effectif.id,
            f"A modifié l'effectif {effectif.niveau_label} {effectif.annee_scolaire} de {effectif.etablissement.nom}",
        )
        db.commit()
    return RedirectResponse(url="/admin/effectifs", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{effectif_id}/delete")
def effectifs_delete(
    effectif_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_effectifs_access_web),
):
    effectif = db.get(models.Effectif, effectif_id)
    if effectif:
        audit.log(
            db, user, "delete", "Effectif", effectif.id,
            f"A supprimé l'effectif {effectif.niveau_label} {effectif.annee_scolaire} de {effectif.etablissement.nom}",
        )
        db.delete(effectif)
        db.commit()
    return RedirectResponse(url="/admin/effectifs", status_code=status.HTTP_303_SEE_OTHER)
