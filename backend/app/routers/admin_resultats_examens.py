from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from .. import audit, models
from ..database import get_db
from ..deps import require_resultats_examens_access_web
from ..reports import current_annee_scolaire, export_resultats_csv

router = APIRouter(prefix="/admin/resultats-examens", tags=["admin-resultats-examens"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def resultats_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_resultats_examens_access_web),
):
    items = (
        db.query(models.ResultatExamen)
        .options(joinedload(models.ResultatExamen.etablissement))
        .order_by(models.ResultatExamen.annee_scolaire.desc(), models.ResultatExamen.id.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/resultats_examens_list.html",
        {"admin": user, "items": items, "active": "resultats_examens"},
    )


@router.get("/export.csv")
def resultats_export_csv(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_resultats_examens_access_web),
):
    csv_content = export_resultats_csv(db)
    return Response(
        content="﻿" + csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="resultats_examens.csv"'},
    )


@router.get("/new")
def resultats_new_form(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_resultats_examens_access_web),
):
    etablissements = db.query(models.Etablissement).order_by(models.Etablissement.nom).all()
    return templates.TemplateResponse(
        request,
        "admin/resultat_examen_form.html",
        {
            "admin": user,
            "item": None,
            "etablissements": etablissements,
            "annee_par_defaut": current_annee_scolaire(),
            "active": "resultats_examens",
        },
    )


@router.post("/new")
def resultats_create(
    etablissement_id: int = Form(...),
    annee_scolaire: str = Form(...),
    type_examen: str = Form(...),
    nombre_inscrits: int = Form(0),
    nombre_admis: int = Form(0),
    nombre_admis_garcons: int = Form(0),
    nombre_admis_filles: int = Form(0),
    is_published: bool = Form(False),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_resultats_examens_access_web),
):
    admis = min(nombre_admis, nombre_inscrits) if nombre_inscrits else nombre_admis
    resultat = models.ResultatExamen(
        etablissement_id=etablissement_id,
        annee_scolaire=annee_scolaire,
        type_examen=type_examen,
        nombre_inscrits=nombre_inscrits,
        nombre_admis=admis,
        nombre_admis_garcons=min(nombre_admis_garcons, admis) if admis else 0,
        nombre_admis_filles=min(nombre_admis_filles, admis) if admis else 0,
        is_published=is_published,
        recorded_by_id=user.id,
    )
    db.add(resultat)
    db.flush()
    audit.log(
        db, user, "create", "Résultat d'examen", resultat.id,
        f"A saisi le résultat {resultat.type_examen} {resultat.annee_scolaire} de {resultat.etablissement.nom}",
    )
    db.commit()
    return RedirectResponse(url="/admin/resultats-examens", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{resultat_id}/edit")
def resultats_edit_form(
    resultat_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_resultats_examens_access_web),
):
    item = db.get(models.ResultatExamen, resultat_id)
    etablissements = db.query(models.Etablissement).order_by(models.Etablissement.nom).all()
    return templates.TemplateResponse(
        request,
        "admin/resultat_examen_form.html",
        {"admin": user, "item": item, "etablissements": etablissements, "active": "resultats_examens"},
    )


@router.post("/{resultat_id}/edit")
def resultats_update(
    resultat_id: int,
    etablissement_id: int = Form(...),
    annee_scolaire: str = Form(...),
    type_examen: str = Form(...),
    nombre_inscrits: int = Form(0),
    nombre_admis: int = Form(0),
    nombre_admis_garcons: int = Form(0),
    nombre_admis_filles: int = Form(0),
    is_published: bool = Form(False),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_resultats_examens_access_web),
):
    resultat = db.get(models.ResultatExamen, resultat_id)
    if resultat:
        admis = min(nombre_admis, nombre_inscrits) if nombre_inscrits else nombre_admis
        resultat.etablissement_id = etablissement_id
        resultat.annee_scolaire = annee_scolaire
        resultat.type_examen = type_examen
        resultat.nombre_inscrits = nombre_inscrits
        resultat.nombre_admis = admis
        resultat.nombre_admis_garcons = min(nombre_admis_garcons, admis) if admis else 0
        resultat.nombre_admis_filles = min(nombre_admis_filles, admis) if admis else 0
        resultat.is_published = is_published
        audit.log(
            db, user, "update", "Résultat d'examen", resultat.id,
            f"A modifié le résultat {resultat.type_examen} {resultat.annee_scolaire} de {resultat.etablissement.nom}",
        )
        db.commit()
    return RedirectResponse(url="/admin/resultats-examens", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{resultat_id}/delete")
def resultats_delete(
    resultat_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_resultats_examens_access_web),
):
    resultat = db.get(models.ResultatExamen, resultat_id)
    if resultat:
        audit.log(
            db, user, "delete", "Résultat d'examen", resultat.id,
            f"A supprimé le résultat {resultat.type_examen} {resultat.annee_scolaire} de {resultat.etablissement.nom}",
        )
        db.delete(resultat)
        db.commit()
    return RedirectResponse(url="/admin/resultats-examens", status_code=status.HTTP_303_SEE_OTHER)
