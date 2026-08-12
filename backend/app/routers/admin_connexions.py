from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_admin_web

router = APIRouter(prefix="/admin/connexions", tags=["admin-connexions"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

PAGE_SIZE = 150


@router.get("")
def connexions_list(
    request: Request,
    user_id: int | None = None,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin_web),
):
    query = db.query(models.ConnexionLog)
    if user_id:
        query = query.filter(models.ConnexionLog.user_id == user_id)

    items = query.order_by(desc(models.ConnexionLog.created_at)).limit(PAGE_SIZE).all()
    users = db.query(models.User).order_by(models.User.full_name).all()

    return templates.TemplateResponse(
        request,
        "admin/connexions_list.html",
        {
            "admin": admin,
            "active": "connexions",
            "items": items,
            "users": users,
            "selected_user_id": user_id,
            "page_size": PAGE_SIZE,
        },
    )
