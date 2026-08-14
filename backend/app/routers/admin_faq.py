from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_publications_access_web

router = APIRouter(prefix="/admin/faq", tags=["admin-faq"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def faq_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    items = db.query(models.Faq).order_by(models.Faq.ordre, models.Faq.id).all()
    return templates.TemplateResponse(
        request,
        "admin/faq_list.html",
        {"admin": user, "items": items, "active": "faq"},
    )


@router.get("/new")
def faq_new_form(
    request: Request,
    user: models.User = Depends(require_publications_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/faq_form.html",
        {"admin": user, "item": None, "active": "faq"},
    )


@router.post("/new")
def faq_create(
    question: str = Form(...),
    reponse: str = Form(...),
    ordre: int = Form(0),
    is_published: bool = Form(False),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    faq = models.Faq(question=question, reponse=reponse, ordre=ordre, is_published=is_published)
    db.add(faq)
    db.commit()
    return RedirectResponse(url="/admin/faq", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{faq_id}/edit")
def faq_edit_form(
    faq_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    item = db.get(models.Faq, faq_id)
    return templates.TemplateResponse(
        request,
        "admin/faq_form.html",
        {"admin": user, "item": item, "active": "faq"},
    )


@router.post("/{faq_id}/edit")
def faq_update(
    faq_id: int,
    question: str = Form(...),
    reponse: str = Form(...),
    ordre: int = Form(0),
    is_published: bool = Form(False),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    faq = db.get(models.Faq, faq_id)
    if faq:
        faq.question = question
        faq.reponse = reponse
        faq.ordre = ordre
        faq.is_published = is_published
        db.commit()
    return RedirectResponse(url="/admin/faq", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{faq_id}/delete")
def faq_delete(
    faq_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    faq = db.get(models.Faq, faq_id)
    if faq:
        db.delete(faq)
        db.commit()
    return RedirectResponse(url="/admin/faq", status_code=status.HTTP_303_SEE_OTHER)
