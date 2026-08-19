from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_publications_access_web

router = APIRouter(prefix="/admin/sondages-express", tags=["admin-sondages-express"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def sondages_express_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    items = (
        db.query(models.SondageExpress)
        .order_by(models.SondageExpress.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/sondages_express_list.html",
        {"admin": user, "items": items, "active": "sondages_express"},
    )


@router.get("/new")
def sondages_express_new_form(
    request: Request,
    user: models.User = Depends(require_publications_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/sondage_express_form.html",
        {"admin": user, "active": "sondages_express", "error": None},
    )


@router.post("/new")
def sondages_express_create(
    request: Request,
    question: str = Form(...),
    option1: str = Form(""),
    option2: str = Form(""),
    option3: str = Form(""),
    option4: str = Form(""),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    textes = [o.strip() for o in [option1, option2, option3, option4] if o.strip()]
    if len(textes) < 2:
        return templates.TemplateResponse(
            request,
            "admin/sondage_express_form.html",
            {"admin": user, "active": "sondages_express", "error": "Indiquez au moins 2 options."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if is_active:
        db.query(models.SondageExpress).update({"is_active": False})

    def _create(active: bool) -> models.SondageExpress:
        sondage = models.SondageExpress(question=question, is_active=active, created_by_id=user.id)
        db.add(sondage)
        db.flush()
        for i, texte in enumerate(textes):
            db.add(models.SondageExpressOption(sondage_id=sondage.id, texte=texte, ordre=i))
        return sondage

    _create(is_active)
    try:
        db.commit()
    except IntegrityError:
        # Un autre sondage a été activé entre-temps par une requête concurrente
        # (index unique partiel "un seul actif à la fois") : on recrée le sondage
        # sans l'activer plutôt que de perdre la saisie de l'admin.
        db.rollback()
        _create(False)
        db.commit()
    return RedirectResponse(url="/admin/sondages-express", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{sondage_id}/activer")
def sondages_express_activer(
    sondage_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    sondage = db.get(models.SondageExpress, sondage_id)
    if sondage:
        db.query(models.SondageExpress).update({"is_active": False})
        sondage.is_active = True
        try:
            db.commit()
        except IntegrityError:
            # Course avec une autre activation concurrente — sans effet, l'autre
            # sondage reste actif ; l'admin peut réessayer si besoin.
            db.rollback()
    return RedirectResponse(url="/admin/sondages-express", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{sondage_id}/desactiver")
def sondages_express_desactiver(
    sondage_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    sondage = db.get(models.SondageExpress, sondage_id)
    if sondage:
        sondage.is_active = False
        db.commit()
    return RedirectResponse(url="/admin/sondages-express", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{sondage_id}/delete")
def sondages_express_delete(
    sondage_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    sondage = db.get(models.SondageExpress, sondage_id)
    if sondage:
        db.delete(sondage)
        db.commit()
    return RedirectResponse(url="/admin/sondages-express", status_code=status.HTTP_303_SEE_OTHER)
