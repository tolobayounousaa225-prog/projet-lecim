"""Boîte à idées interne — suggestions soumises par les membres du BEN et les
établissements affiliés, votables par tous les comptes connectés (mêmes votants,
mêmes idées, quel que soit le portail), pour aider à prioriser les prochains
chantiers de la plateforme."""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_admin_web, require_etablissement_login_web, require_login_web

router = APIRouter(tags=["idees"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def _ordered_idees(db: Session) -> list[models.Idee]:
    items = db.query(models.Idee).all()
    return sorted(items, key=lambda i: (-i.nombre_votes, i.created_at.timestamp() * -1))


# ---------- Espace admin (BEN) ----------

@router.get("/admin/idees")
def admin_idees_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_web),
):
    return templates.TemplateResponse(
        request,
        "admin/idees_list.html",
        {"admin": user, "items": _ordered_idees(db), "active": "idees"},
    )


@router.post("/admin/idees/new")
def admin_idees_create(
    titre: str = Form(...),
    description: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_web),
):
    db.add(models.Idee(titre=titre, description=description, auteur_id=user.id))
    db.commit()
    return RedirectResponse(url="/admin/idees", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/admin/idees/{idee_id}/vote")
def admin_idees_vote(
    idee_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_web),
):
    _toggle_vote(db, idee_id, user.id)
    return RedirectResponse(url="/admin/idees", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/admin/idees/{idee_id}/statut")
def admin_idees_statut(
    idee_id: int,
    statut: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin_web),
):
    idee = db.get(models.Idee, idee_id)
    if idee and statut in {"nouvelle", "en_etude", "retenue", "rejetee"}:
        idee.statut = statut
        db.commit()
    return RedirectResponse(url="/admin/idees", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Espace établissement ----------

@router.get("/etablissement/idees")
def etablissement_idees_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etablissement_login_web),
):
    return templates.TemplateResponse(
        request,
        "etablissement/idees.html",
        {"user": user, "etablissement": user.etablissement, "items": _ordered_idees(db), "active": "idees"},
    )


@router.post("/etablissement/idees/new")
def etablissement_idees_create(
    titre: str = Form(...),
    description: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etablissement_login_web),
):
    db.add(models.Idee(titre=titre, description=description, auteur_id=user.id))
    db.commit()
    return RedirectResponse(url="/etablissement/idees", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/etablissement/idees/{idee_id}/vote")
def etablissement_idees_vote(
    idee_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etablissement_login_web),
):
    _toggle_vote(db, idee_id, user.id)
    return RedirectResponse(url="/etablissement/idees", status_code=status.HTTP_303_SEE_OTHER)


def _toggle_vote(db: Session, idee_id: int, user_id: int) -> None:
    idee = db.get(models.Idee, idee_id)
    if not idee:
        return
    existing = (
        db.query(models.IdeeVote)
        .filter(models.IdeeVote.idee_id == idee_id, models.IdeeVote.user_id == user_id)
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()
        return
    db.add(models.IdeeVote(idee_id=idee_id, user_id=user_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
