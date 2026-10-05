import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import audit, models
from ..database import get_db
from ..deps import require_delegation_management_web
from ..reports import current_annee_scolaire, generate_delegation_report_pdf
from ..security import hash_password, password_policy_error
from ..security_utils import safe_content_disposition

router = APIRouter(prefix="/admin/delegations", tags=["admin-delegations"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Seuils (en jours) utilisés pour signaler une délégation inactive sur la liste admin.
INACTIVITE_SEUIL_ALERTE = 120
INACTIVITE_SEUIL_SURVEILLANCE = 60


@router.get("")
def delegations_list(
    request: Request,
    error: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_management_web),
):
    items = db.query(models.Delegation).order_by(models.Delegation.nom).all()

    dernieres_reunions = dict(
        db.query(models.Reunion.delegation_id, func.max(models.Reunion.date))
        .filter(models.Reunion.delegation_id.isnot(None))
        .group_by(models.Reunion.delegation_id)
        .all()
    )
    today = datetime.date.today()
    activite = {}
    for item in items:
        derniere = dernieres_reunions.get(item.id)
        jours = (today - derniere).days if derniere else None
        if jours is None:
            niveau = "alerte"
        elif jours > INACTIVITE_SEUIL_ALERTE:
            niveau = "alerte"
        elif jours > INACTIVITE_SEUIL_SURVEILLANCE:
            niveau = "surveillance"
        else:
            niveau = "actif"
        activite[item.id] = {"derniere_reunion": derniere, "jours": jours, "niveau": niveau}

    return templates.TemplateResponse(
        request,
        "admin/delegations_list.html",
        {"admin": user, "items": items, "activite": activite, "active": "delegations", "error": error},
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
        blockers = []
        if db.query(models.User).filter(models.User.delegation_id == delegation_id).first():
            blockers.append("des comptes")
        if db.query(models.Etablissement).filter(models.Etablissement.delegation_id == delegation_id).first():
            blockers.append("des établissements")
        if db.query(models.Membre).filter(models.Membre.delegation_id == delegation_id).first():
            blockers.append("des membres")
        if db.query(models.Reunion).filter(models.Reunion.delegation_id == delegation_id).first():
            blockers.append("des réunions")
        if db.query(models.AnnonceDelegation).filter(models.AnnonceDelegation.delegation_id == delegation_id).first():
            blockers.append("des annonces")
        if blockers:
            message = f"Impossible de supprimer « {delegation.nom} » : elle a encore {', '.join(blockers)} rattaché(e)s. Retirez-les d'abord."
            return RedirectResponse(url=f"/admin/delegations?error={quote(message)}", status_code=status.HTTP_303_SEE_OTHER)
        audit.log(db, user, "delete", "Délégation", delegation.id, f"A supprimé la délégation {delegation.nom}")
        db.delete(delegation)
        db.commit()
    return RedirectResponse(url="/admin/delegations", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{delegation_id}")
def delegation_detail(
    delegation_id: int,
    request: Request,
    error: str | None = None,
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
            "error": error,
        },
    )


@router.get("/{delegation_id}/rapport.pdf")
def delegation_rapport_pdf(
    delegation_id: int,
    annee_scolaire: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_management_web),
):
    delegation = db.get(models.Delegation, delegation_id)
    if not delegation:
        return RedirectResponse(url="/admin/delegations", status_code=status.HTTP_303_SEE_OTHER)
    annee = annee_scolaire or current_annee_scolaire()
    today = datetime.date.today()
    debut_annee = datetime.date(today.year if today.month >= 9 else today.year - 1, 9, 1)
    pdf_bytes = generate_delegation_report_pdf(db, delegation, annee, debut_annee, today, user)
    filename = safe_content_disposition(f"rapport-delegation-{delegation.nom}.pdf".replace(" ", "-"))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
    password_error = password_policy_error(password)
    if existing or password_error:
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
                "error": "Un compte existe déjà avec cet e-mail." if existing else password_error,
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
    try:
        db.flush()
    except IntegrityError:
        # Course avec une autre création concurrente utilisant le même e-mail —
        # la contrainte unique a bloqué la seconde requête plutôt que de laisser
        # un doublon.
        db.rollback()
        return RedirectResponse(
            url=f"/admin/delegations/{delegation_id}?error={quote('Conflit détecté (e-mail déjà pris entre-temps) — veuillez réessayer.')}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
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
