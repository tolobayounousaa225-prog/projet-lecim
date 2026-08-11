from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_admin_web

router = APIRouter(prefix="/admin/audit", tags=["admin-audit"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

PAGE_SIZE = 100


@router.get("")
def audit_list(
    request: Request,
    user_id: int | None = None,
    entity_type: str | None = None,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin_web),
):
    query = db.query(models.AuditLog)
    if user_id:
        query = query.filter(models.AuditLog.user_id == user_id)
    if entity_type:
        query = query.filter(models.AuditLog.entity_type == entity_type)

    items = query.order_by(desc(models.AuditLog.created_at)).limit(PAGE_SIZE).all()
    users = db.query(models.User).order_by(models.User.full_name).all()
    entity_types = [
        row[0] for row in db.query(models.AuditLog.entity_type).distinct().order_by(models.AuditLog.entity_type).all()
    ]

    return templates.TemplateResponse(
        request,
        "admin/audit_list.html",
        {
            "admin": admin,
            "active": "audit",
            "items": items,
            "users": users,
            "entity_types": entity_types,
            "selected_user_id": user_id,
            "selected_entity_type": entity_type,
            "page_size": PAGE_SIZE,
        },
    )
