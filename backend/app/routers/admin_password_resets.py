from pathlib import Path

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from .. import models
from ..database import get_db
from ..deps import require_admin_web

router = APIRouter(prefix="/admin/reinitialisations", tags=["admin-password-resets"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def password_resets_list(
    request: Request,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin_web),
):
    items = (
        db.query(models.PasswordResetRequest)
        .options(joinedload(models.PasswordResetRequest.user))
        .filter(models.PasswordResetRequest.used.is_(False))
        .order_by(desc(models.PasswordResetRequest.created_at))
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/password_resets_list.html",
        {"admin": admin, "items": items, "active": "reinitialisations"},
    )


@router.post("/{request_id}/masquer")
def password_reset_dismiss(
    request_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin_web),
):
    item = db.get(models.PasswordResetRequest, request_id)
    if item:
        item.used = True
        db.commit()
    return RedirectResponse(url="/admin/reinitialisations", status_code=status.HTTP_303_SEE_OTHER)
