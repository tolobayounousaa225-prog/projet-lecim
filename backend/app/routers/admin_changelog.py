"""Journal des nouveautés/correctifs de la plateforme — consultable par tout le
bureau, alimenté par un administrateur, pour informer sans passer par un canal
externe."""

import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_admin_web, require_login_web
from ..models import CHANGELOG_CATEGORIES

router = APIRouter(prefix="/admin/changelog", tags=["admin-changelog"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def changelog_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_web),
):
    items = db.query(models.ChangelogEntry).order_by(models.ChangelogEntry.published_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin/changelog_list.html",
        {"admin": user, "items": items, "categories": CHANGELOG_CATEGORIES, "active": "changelog"},
    )


@router.post("/new")
def changelog_create(
    titre: str = Form(...),
    description: str = Form(""),
    categorie: str = Form("nouveaute"),
    published_at: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin_web),
):
    entry = models.ChangelogEntry(
        titre=titre,
        description=description or None,
        categorie=categorie if categorie in CHANGELOG_CATEGORIES else "nouveaute",
        published_at=datetime.date.fromisoformat(published_at) if published_at else datetime.date.today(),
        created_by_id=user.id,
    )
    db.add(entry)
    db.commit()
    return RedirectResponse(url="/admin/changelog", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{entry_id}/delete")
def changelog_delete(
    entry_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin_web),
):
    entry = db.get(models.ChangelogEntry, entry_id)
    if entry:
        db.delete(entry)
        db.commit()
    return RedirectResponse(url="/admin/changelog", status_code=status.HTTP_303_SEE_OTHER)
