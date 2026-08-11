from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import audit, models
from ..database import get_db
from ..deps import require_delegation_management_web
from ..security import hash_password

router = APIRouter(prefix="/admin/delegations", tags=["admin-delegations"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def delegations_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_management_web),
):
    items = db.query(models.Delegation).order_by(models.Delegation.nom).all()
    return templates.TemplateResponse(
        request,
        "admin/delegations_list.html",
        {"admin": user, "items": items, "active": "delegations"},
    )


@router.get("/new")
def delegations_new_form(
    request: Request,
    user: models.User = Depends(require_delegation_management_web),
):
    return templates.TemplateResponse(
        request,
        "admin/delegation_form.html",
        {"admin": user, "item": None, "active": "delegations"},
    )


@router.post("/new")
def delegations_create(
    nom: str = Form(...),
    region: str = Form(""),
    latitude: str = Form(""),
    longitude: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_management_web),
):
    delegation = models.Delegation(
        nom=nom,
        region=region or None,
        latitude=float(latitude) if latitude else None,
        longitude=float(longitude) if longitude else None,
        created_by_id=user.id,
    )
    db.add(delegation)
    db.flush()
    audit.log(db, user, "create", "Délégation", delegation.id, f"A créé la délégation {delegation.nom}")
    db.commit()
    return RedirectResponse(url="/admin/delegations", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{delegation_id}/edit")
def delegations_edit_form(
    delegation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_management_web),
):
    item = db.get(models.Delegation, delegation_id)
    return templates.TemplateResponse(
        request,
        "admin/delegation_form.html",
        {"admin": user, "item": item, "active": "delegations"},
    )


@router.post("/{delegation_id}/edit")
def delegations_update(
    delegation_id: int,
    nom: str = Form(...),
    region: str = Form(""),
    latitude: str = Form(""),
    longitude: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_management_web),
):
    delegation = db.get(models.Delegation, delegation_id)
    if delegation:
        delegation.nom = nom
        delegation.region = region or None
        delegation.latitude = float(latitude) if latitude else None
        delegation.longitude = float(longitude) if longitude else None
        db.commit()
    return RedirectResponse(url="/admin/delegations", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{delegation_id}/delete")
def delegations_delete(
    delegation_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_management_web),
):
    delegation = db.get(models.Delegation, delegation_id)
    if delegation:
        audit.log(db, user, "delete", "Délégation", delegation.id, f"A supprimé la délégation {delegation.nom}")
        db.delete(delegation)
        db.commit()
    return RedirectResponse(url="/admin/delegations", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{delegation_id}")
def delegation_detail(
    delegation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_management_web),
):
    delegation = db.get(models.Delegation, delegation_id)
    if not delegation:
        return RedirectResponse(url="/admin/delegations", status_code=status.HTTP_303_SEE_OTHER)
    comptes = db.query(models.User).filter(models.User.delegation_id == delegation_id).all()
    etablissements = (
        db.query(models.Etablissement).filter(models.Etablissement.delegation_id == delegation_id).all()
    )
    reunions_count = db.query(models.Reunion).filter(models.Reunion.delegation_id == delegation_id).count()
    membres_count = db.query(models.Membre).filter(models.Membre.delegation_id == delegation_id).count()
    return templates.TemplateResponse(
        request,
        "admin/delegation_detail.html",
        {
            "admin": user,
            "delegation": delegation,
            "comptes": comptes,
            "etablissements": etablissements,
            "reunions_count": reunions_count,
            "membres_count": membres_count,
            "active": "delegations",
            "error": None,
        },
    )


@router.post("/{delegation_id}/users/new")
def delegation_user_create(
    delegation_id: int,
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role_local: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_management_web),
):
    delegation = db.get(models.Delegation, delegation_id)
    if not delegation:
        return RedirectResponse(url="/admin/delegations", status_code=status.HTTP_303_SEE_OTHER)

    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        comptes = db.query(models.User).filter(models.User.delegation_id == delegation_id).all()
        etablissements = (
            db.query(models.Etablissement)
            .filter(models.Etablissement.delegation_id == delegation_id)
            .all()
        )
        return templates.TemplateResponse(
            request,
            "admin/delegation_detail.html",
            {
                "admin": user,
                "delegation": delegation,
                "comptes": comptes,
                "etablissements": etablissements,
                "reunions_count": db.query(models.Reunion)
                .filter(models.Reunion.delegation_id == delegation_id)
                .count(),
                "membres_count": db.query(models.Membre)
                .filter(models.Membre.delegation_id == delegation_id)
                .count(),
                "active": "delegations",
                "error": "Un compte existe déjà avec cet e-mail.",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    delegation_user = models.User(
        full_name=full_name,
        email=email,
        hashed_password=hash_password(password),
        access_level="bureau",
        delegation_id=delegation_id,
        role_local=role_local or None,
    )
    db.add(delegation_user)
    db.flush()
    audit.log(db, user, "create", "Compte délégation", delegation_user.id, f"A créé le compte {delegation_user.full_name} pour la délégation {delegation.nom}")
    db.commit()
    return RedirectResponse(url=f"/admin/delegations/{delegation_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{delegation_id}/users/{user_id}/delete")
def delegation_user_delete(
    delegation_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_management_web),
):
    target = db.get(models.User, user_id)
    if target and target.delegation_id == delegation_id:
        audit.log(db, user, "delete", "Compte délégation", target.id, f"A révoqué le compte {target.full_name} de la délégation #{delegation_id}")
        db.delete(target)
        db.commit()
    return RedirectResponse(url=f"/admin/delegations/{delegation_id}", status_code=status.HTTP_303_SEE_OTHER)
