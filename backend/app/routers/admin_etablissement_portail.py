import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import audit, models
from ..database import get_db
from ..deps import require_finance_access_web
from ..security import hash_password

router = APIRouter(prefix="/admin", tags=["admin-etablissement-portail"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/etablissements/{etablissement_id}/compte")
def etablissement_compte(
    etablissement_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    etablissement = db.get(models.Etablissement, etablissement_id)
    if not etablissement:
        return RedirectResponse(url="/admin/etablissements", status_code=status.HTTP_303_SEE_OTHER)
    compte = db.query(models.User).filter(models.User.etablissement_id == etablissement_id).first()
    return templates.TemplateResponse(
        request,
        "admin/etablissement_compte.html",
        {"admin": user, "etablissement": etablissement, "compte": compte, "active": "finances", "error": None},
    )


@router.post("/etablissements/{etablissement_id}/compte/new")
def etablissement_compte_create(
    etablissement_id: int,
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    etablissement = db.get(models.Etablissement, etablissement_id)
    if not etablissement:
        return RedirectResponse(url="/admin/etablissements", status_code=status.HTTP_303_SEE_OTHER)

    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        return templates.TemplateResponse(
            request,
            "admin/etablissement_compte.html",
            {
                "admin": user,
                "etablissement": etablissement,
                "compte": None,
                "active": "finances",
                "error": "Un compte existe déjà avec cet e-mail.",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    compte = models.User(
        full_name=full_name,
        email=email,
        hashed_password=hash_password(password),
        access_level="bureau",
        etablissement_id=etablissement_id,
    )
    db.add(compte)
    db.flush()
    audit.log(db, user, "create", "Compte établissement", compte.id, f"A créé le compte de {etablissement.nom}")
    db.commit()
    return RedirectResponse(url=f"/admin/etablissements/{etablissement_id}/compte", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/etablissements/{etablissement_id}/compte/delete")
def etablissement_compte_delete(
    etablissement_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    compte = db.query(models.User).filter(models.User.etablissement_id == etablissement_id).first()
    if compte:
        audit.log(db, user, "delete", "Compte établissement", compte.id, f"A révoqué le compte établissement #{etablissement_id}")
        db.delete(compte)
        db.commit()
    return RedirectResponse(url=f"/admin/etablissements/{etablissement_id}/compte", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Demandes soumises par les établissements ----------

@router.get("/demandes-etablissements")
def demandes_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    items = db.query(models.DemandeEtablissement).order_by(models.DemandeEtablissement.created_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin/demandes_etablissements_list.html",
        {"admin": user, "items": items, "active": "demandes_etablissements"},
    )


@router.post("/demandes-etablissements/{demande_id}/repondre")
def demande_repondre(
    demande_id: int,
    reponse: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    demande = db.get(models.DemandeEtablissement, demande_id)
    if demande:
        demande.reponse = reponse or None
        demande.statut = "traitee"
        demande.traitee_at = datetime.datetime.utcnow()
        audit.log(db, user, "update", "Demande établissement", demande.id, f"A répondu à la demande « {demande.objet} » de {demande.etablissement.nom}")
        db.commit()
    return RedirectResponse(url="/admin/demandes-etablissements", status_code=status.HTTP_303_SEE_OTHER)
