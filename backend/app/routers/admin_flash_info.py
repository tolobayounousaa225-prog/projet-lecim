from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_news_access_web

router = APIRouter(prefix="/admin/flash-info", tags=["admin-flash-info"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def flash_info_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_news_access_web),
):
    items = db.query(models.FlashInfo).order_by(models.FlashInfo.ordre, models.FlashInfo.id).all()
    return templates.TemplateResponse(
        request,
        "admin/flash_info_list.html",
        {"admin": user, "items": items, "active": "flash_info"},
    )


@router.post("/new")
def flash_info_create(
    message: str = Form(...),
    lien: str = Form(""),
    ordre: int = Form(0),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_news_access_web),
):
    db.add(
        models.FlashInfo(
            message=message,
            lien=lien or None,
            ordre=ordre,
            is_active=is_active,
            created_by_id=user.id,
        )
    )
    db.commit()
    return RedirectResponse(url="/admin/flash-info", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{entry_id}/edit")
def flash_info_edit_form(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_news_access_web),
):
    item = db.get(models.FlashInfo, entry_id)
    if not item:
        return RedirectResponse(url="/admin/flash-info", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request,
        "admin/flash_info_form.html",
        {"admin": user, "item": item, "active": "flash_info"},
    )


@router.post("/{entry_id}/edit")
def flash_info_update(
    entry_id: int,
    message: str = Form(...),
    lien: str = Form(""),
    ordre: int = Form(0),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_news_access_web),
):
    item = db.get(models.FlashInfo, entry_id)
    if item:
        item.message = message
        item.lien = lien or None
        item.ordre = ordre
        item.is_active = is_active
        db.commit()
    return RedirectResponse(url="/admin/flash-info", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{entry_id}/toggle")
def flash_info_toggle(
    entry_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_news_access_web),
):
    item = db.get(models.FlashInfo, entry_id)
    if item:
        item.is_active = not item.is_active
        db.commit()
    return RedirectResponse(url="/admin/flash-info", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{entry_id}/delete")
def flash_info_delete(
    entry_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_news_access_web),
):
    item = db.get(models.FlashInfo, entry_id)
    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse(url="/admin/flash-info", status_code=status.HTTP_303_SEE_OTHER)
