import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_login_web

router = APIRouter(prefix="/admin/taches", tags=["admin-taches"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def _my_tache_or_none(db: Session, tache_id: int, user: models.User) -> models.TachePersonnelle | None:
    """N'importe qui de connecté peut deviner un ID — on ne renvoie jamais la
    tâche d'un autre utilisateur, même en lecture."""
    item = db.get(models.TachePersonnelle, tache_id)
    if not item or item.user_id != user.id:
        return None
    return item


@router.get("")
def taches_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_web),
):
    items = (
        db.query(models.TachePersonnelle)
        .filter(models.TachePersonnelle.user_id == user.id)
        .order_by(models.TachePersonnelle.is_done, models.TachePersonnelle.echeance.is_(None), models.TachePersonnelle.echeance, models.TachePersonnelle.id.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/taches_list.html",
        {"admin": user, "items": items, "active": "taches", "today": datetime.date.today()},
    )


@router.post("/new")
def taches_create(
    titre: str = Form(...),
    description: str = Form(""),
    echeance: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_web),
):
    echeance_date = None
    if echeance:
        try:
            echeance_date = datetime.date.fromisoformat(echeance)
        except ValueError:
            echeance_date = None
    db.add(
        models.TachePersonnelle(
            user_id=user.id, titre=titre, description=description or None, echeance=echeance_date,
        )
    )
    db.commit()
    return RedirectResponse(url="/admin/taches", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{tache_id}/toggle")
def taches_toggle(
    tache_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_web),
):
    item = _my_tache_or_none(db, tache_id, user)
    if item:
        item.is_done = not item.is_done
        db.commit()
    return RedirectResponse(url="/admin/taches", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{tache_id}/delete")
def taches_delete(
    tache_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_web),
):
    item = _my_tache_or_none(db, tache_id, user)
    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse(url="/admin/taches", status_code=status.HTTP_303_SEE_OTHER)
