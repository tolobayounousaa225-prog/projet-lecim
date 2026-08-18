"""Suivi admin des abonnés à la newsletter mensuelle — l'inscription se fait
uniquement depuis la vitrine (newsletter_public.py) ; l'admin peut consulter la
liste, retirer un abonné (nettoyage) et déclencher un envoi manuel si besoin."""

from pathlib import Path

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import audit, models
from ..database import get_db
from ..deps import require_publications_access_web
from ..newsletter import run_monthly_newsletter

router = APIRouter(prefix="/admin/newsletter", tags=["admin-newsletter"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def newsletter_list(
    request: Request,
    envoyes: int | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    items = db.query(models.NewsletterSubscriber).order_by(models.NewsletterSubscriber.created_at.desc()).all()
    nb_actifs = sum(1 for i in items if i.is_active)
    return templates.TemplateResponse(
        request,
        "admin/newsletter_list.html",
        {"admin": user, "items": items, "nb_actifs": nb_actifs, "envoyes": envoyes, "active": "newsletter"},
    )


@router.post("/{subscriber_id}/delete")
def newsletter_delete(
    subscriber_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    subscriber = db.get(models.NewsletterSubscriber, subscriber_id)
    if subscriber:
        audit.log(db, user, "delete", "Abonné newsletter", subscriber.id, f"A retiré l'abonné newsletter {subscriber.email}")
        db.delete(subscriber)
        db.commit()
    return RedirectResponse(url="/admin/newsletter", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/envoyer-maintenant")
def newsletter_envoyer_maintenant(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    envoyes = run_monthly_newsletter()
    audit.log(db, user, "create", "Newsletter", None, f"A déclenché manuellement l'envoi de la newsletter ({envoyes} e-mails)")
    db.commit()
    return RedirectResponse(url=f"/admin/newsletter?envoyes={envoyes}", status_code=status.HTTP_303_SEE_OTHER)
