from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_messagerie_access_web
from ..notifications import notify

router = APIRouter(prefix="/admin/messagerie", tags=["admin-messagerie"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def messagerie_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_messagerie_access_web),
):
    etablissements = db.query(models.Etablissement).order_by(models.Etablissement.nom).all()
    last_message_at = dict(
        db.query(models.MessageEtablissement.etablissement_id, func.max(models.MessageEtablissement.created_at))
        .group_by(models.MessageEtablissement.etablissement_id)
        .all()
    )
    unread_counts = dict(
        db.query(models.MessageEtablissement.etablissement_id, func.count(models.MessageEtablissement.id))
        .filter(
            models.MessageEtablissement.is_from_ben.is_(False),
            models.MessageEtablissement.is_read_by_ben.is_(False),
        )
        .group_by(models.MessageEtablissement.etablissement_id)
        .all()
    )
    rows = sorted(
        (
            {
                "etablissement": e,
                "last_message_at": last_message_at.get(e.id),
                "unread": unread_counts.get(e.id, 0),
            }
            for e in etablissements
        ),
        key=lambda r: (r["last_message_at"] is None, r["last_message_at"] and -r["last_message_at"].timestamp() or 0),
    )
    return templates.TemplateResponse(
        request,
        "admin/messagerie_list.html",
        {"admin": user, "rows": rows, "active": "messagerie"},
    )


@router.get("/{etablissement_id}")
def messagerie_thread(
    etablissement_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_messagerie_access_web),
):
    etablissement = db.get(models.Etablissement, etablissement_id)
    if not etablissement:
        return RedirectResponse(url="/admin/messagerie", status_code=status.HTTP_303_SEE_OTHER)
    messages = (
        db.query(models.MessageEtablissement)
        .filter(models.MessageEtablissement.etablissement_id == etablissement_id)
        .order_by(models.MessageEtablissement.created_at)
        .all()
    )
    unread = [m for m in messages if not m.is_from_ben and not m.is_read_by_ben]
    for m in unread:
        m.is_read_by_ben = True
    if unread:
        db.commit()
    return templates.TemplateResponse(
        request,
        "admin/messagerie_thread.html",
        {"admin": user, "etablissement": etablissement, "messages": messages, "active": "messagerie"},
    )


@router.post("/{etablissement_id}/new")
def messagerie_reply(
    etablissement_id: int,
    body: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_messagerie_access_web),
):
    etablissement = db.get(models.Etablissement, etablissement_id)
    if etablissement:
        message = models.MessageEtablissement(
            etablissement_id=etablissement_id,
            sender_id=user.id,
            is_from_ben=True,
            body=body,
        )
        db.add(message)
        compte = db.query(models.User).filter(models.User.etablissement_id == etablissement_id).all()
        for c in compte:
            notify(db, c.id, f"Nouveau message du BEN concernant {etablissement.nom}.", link="/etablissement/messagerie")
        db.commit()
    return RedirectResponse(url=f"/admin/messagerie/{etablissement_id}", status_code=status.HTTP_303_SEE_OTHER)
