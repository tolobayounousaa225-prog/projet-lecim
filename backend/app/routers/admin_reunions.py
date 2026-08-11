import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import audit, models
from ..database import get_db
from ..deps import require_membres_access_web, require_reunions_access_web
from ..postes import POSTES
from ..reminders import send_reminder_for_reunion

router = APIRouter(prefix="/admin", tags=["admin-reunions"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


# ---------- Membres (répertoire permanent) ----------

@router.get("/membres")
def membres_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_membres_access_web),
):
    items = (
        db.query(models.Membre)
        .filter(models.Membre.delegation_id.is_(None))
        .order_by(models.Membre.full_name)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/membres_list.html",
        {"admin": user, "items": items, "active": "membres"},
    )


@router.get("/membres/new")
def membres_new_form(
    request: Request,
    user: models.User = Depends(require_membres_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/membre_form.html",
        {"admin": user, "item": None, "postes": POSTES, "active": "membres"},
    )


@router.post("/membres/new")
def membres_create(
    full_name: str = Form(...),
    poste: str = Form(""),
    is_adjoint: bool = Form(False),
    phone: str = Form(""),
    email: str = Form(""),
    mandat_debut: str = Form(""),
    mandat_fin: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_membres_access_web),
):
    membre = models.Membre(
        full_name=full_name,
        poste=poste or None,
        is_adjoint=is_adjoint,
        phone=phone or None,
        email=email or None,
        mandat_debut=datetime.date.fromisoformat(mandat_debut) if mandat_debut else None,
        mandat_fin=datetime.date.fromisoformat(mandat_fin) if mandat_fin else None,
    )
    db.add(membre)
    db.commit()
    return RedirectResponse(url="/admin/membres", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/membres/{membre_id}/edit")
def membres_edit_form(
    membre_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_membres_access_web),
):
    item = db.get(models.Membre, membre_id)
    return templates.TemplateResponse(
        request,
        "admin/membre_form.html",
        {"admin": user, "item": item, "postes": POSTES, "active": "membres"},
    )


@router.post("/membres/{membre_id}/edit")
def membres_update(
    membre_id: int,
    full_name: str = Form(...),
    poste: str = Form(""),
    is_adjoint: bool = Form(False),
    phone: str = Form(""),
    email: str = Form(""),
    mandat_debut: str = Form(""),
    mandat_fin: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_membres_access_web),
):
    membre = db.get(models.Membre, membre_id)
    if membre:
        membre.full_name = full_name
        membre.poste = poste or None
        membre.is_adjoint = is_adjoint
        membre.phone = phone or None
        membre.email = email or None
        new_mandat_fin = datetime.date.fromisoformat(mandat_fin) if mandat_fin else None
        if new_mandat_fin != membre.mandat_fin:
            membre.mandat_alert_sent = False
        membre.mandat_debut = datetime.date.fromisoformat(mandat_debut) if mandat_debut else None
        membre.mandat_fin = new_mandat_fin
        db.commit()
    return RedirectResponse(url="/admin/membres", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/membres/{membre_id}/delete")
def membres_delete(
    membre_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_membres_access_web),
):
    membre = db.get(models.Membre, membre_id)
    if membre:
        db.delete(membre)
        db.commit()
    return RedirectResponse(url="/admin/membres", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Réunions ----------

@router.get("/reunions")
def reunions_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    items = (
        db.query(models.Reunion)
        .filter(models.Reunion.delegation_id.is_(None))
        .order_by(models.Reunion.date.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/reunions_list.html",
        {"admin": user, "items": items, "active": "reunions"},
    )


@router.get("/reunions/new")
def reunions_new_form(
    request: Request,
    user: models.User = Depends(require_reunions_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/reunion_form.html",
        {"admin": user, "item": None, "today": datetime.date.today(), "active": "reunions"},
    )


@router.post("/reunions/new")
def reunions_create(
    title: str = Form(...),
    date: datetime.date = Form(...),
    lieu: str = Form(""),
    ordre_du_jour: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    reunion = models.Reunion(
        title=title,
        date=date,
        lieu=lieu or None,
        ordre_du_jour=ordre_du_jour or None,
        created_by_id=user.id,
    )
    db.add(reunion)
    db.commit()
    db.refresh(reunion)
    return RedirectResponse(url=f"/admin/reunions/{reunion.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/reunions/{reunion_id}/edit")
def reunions_edit_form(
    reunion_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    item = db.get(models.Reunion, reunion_id)
    return templates.TemplateResponse(
        request,
        "admin/reunion_form.html",
        {"admin": user, "item": item, "active": "reunions"},
    )


@router.post("/reunions/{reunion_id}/edit")
def reunions_update(
    reunion_id: int,
    title: str = Form(...),
    date: datetime.date = Form(...),
    lieu: str = Form(""),
    ordre_du_jour: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    reunion = db.get(models.Reunion, reunion_id)
    if reunion:
        reunion.title = title
        reunion.date = date
        reunion.lieu = lieu or None
        reunion.ordre_du_jour = ordre_du_jour or None
        db.commit()
    return RedirectResponse(url=f"/admin/reunions/{reunion_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/reunions/{reunion_id}/delete")
def reunions_delete(
    reunion_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    reunion = db.get(models.Reunion, reunion_id)
    if reunion:
        db.delete(reunion)
        db.commit()
    return RedirectResponse(url="/admin/reunions", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/reunions/{reunion_id}")
def reunion_detail(
    reunion_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    reunion = db.get(models.Reunion, reunion_id)
    if not reunion:
        return RedirectResponse(url="/admin/reunions", status_code=status.HTTP_303_SEE_OTHER)

    # Complète la feuille de présence pour les membres ajoutés au répertoire
    # après la création de la réunion.
    existing_membre_ids = {p.membre_id for p in reunion.presences}
    all_membres = (
        db.query(models.Membre)
        .filter(models.Membre.delegation_id.is_(None))
        .order_by(models.Membre.full_name)
        .all()
    )
    for membre in all_membres:
        if membre.id not in existing_membre_ids:
            db.add(models.Presence(reunion_id=reunion.id, membre_id=membre.id, present=False))
    db.commit()
    db.refresh(reunion)

    presences = sorted(reunion.presences, key=lambda p: p.membre.full_name)

    return templates.TemplateResponse(
        request,
        "admin/reunion_detail.html",
        {"admin": user, "reunion": reunion, "presences": presences, "active": "reunions"},
    )


@router.post("/reunions/{reunion_id}/rappel")
def reunion_rappel(
    reunion_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    reunion = db.get(models.Reunion, reunion_id)
    if reunion:
        envoyes = send_reminder_for_reunion(db, reunion)
        audit.log(db, user, "update", "Réunion", reunion.id, f"A envoyé un rappel pour la réunion « {reunion.title} » ({envoyes} e-mail(s))")
        db.commit()
    return RedirectResponse(url=f"/admin/reunions/{reunion_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/reunions/{reunion_id}/presence")
async def reunion_presence_save(
    reunion_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    form = await request.form()
    present_ids = {int(v) for k, v in form.multi_items() if k == "present"}

    presences = db.query(models.Presence).filter(models.Presence.reunion_id == reunion_id).all()
    for presence in presences:
        presence.present = presence.membre_id in present_ids
    db.commit()
    return RedirectResponse(url=f"/admin/reunions/{reunion_id}", status_code=status.HTTP_303_SEE_OTHER)
