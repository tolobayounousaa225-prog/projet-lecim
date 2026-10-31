from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_delegations_access_web
from ..notifications import notify

router = APIRouter(prefix="/admin/messagerie-delegations", tags=["admin-messagerie-delegations"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def messagerie_delegations_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegations_access_web),
):
    delegations = db.query(models.Delegation).order_by(models.Delegation.nom).all()
    last_message_at = dict(
        db.query(models.MessageDelegation.delegation_id, func.max(models.MessageDelegation.created_at))
        .group_by(models.MessageDelegation.delegation_id)
        .all()
    )
    unread_counts = dict(
        db.query(models.MessageDelegation.delegation_id, func.count(models.MessageDelegation.id))
        .filter(
            models.MessageDelegation.is_from_ben.is_(False),
            models.MessageDelegation.is_read_by_ben.is_(False),
        )
        .group_by(models.MessageDelegation.delegation_id)
        .all()
    )
    rows = sorted(
        (
            {
                "delegation": d,
                "last_message_at": last_message_at.get(d.id),
                "unread": unread_counts.get(d.id, 0),
            }
            for d in delegations
        ),
        key=lambda r: (r["last_message_at"] is None, r["last_message_at"] and -r["last_message_at"].timestamp() or 0),
    )
    return templates.TemplateResponse(
        request,
        "admin/messagerie_delegations_list.html",
        {"admin": user, "rows": rows, "active": "messagerie_delegations"},
    )


@router.get("/{delegation_id}")
def messagerie_delegation_thread(
    delegation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegations_access_web),
):
    delegation = db.get(models.Delegation, delegation_id)
    if not delegation:
        return RedirectResponse(url="/admin/messagerie-delegations", status_code=status.HTTP_303_SEE_OTHER)
    messages = (
        db.query(models.MessageDelegation)
        .filter(models.MessageDelegation.delegation_id == delegation_id)
        .order_by(models.MessageDelegation.created_at)
        .all()
    )
    unread = [m for m in messages if not m.is_from_ben and not m.is_read_by_ben]
    for m in unread:
        m.is_read_by_ben = True
    if unread:
        db.commit()
    return templates.TemplateResponse(
        request,
        "admin/messagerie_delegation_thread.html",
        {"admin": user, "delegation": delegation, "messages": messages, "active": "messagerie_delegations"},
    )


@router.post("/{delegation_id}/new")
def messagerie_delegation_reply(
    delegation_id: int,
    body: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegations_access_web),
):
    delegation = db.get(models.Delegation, delegation_id)
    if delegation:
        message = models.MessageDelegation(
            delegation_id=delegation_id,
            sender_id=user.id,
            is_from_ben=True,
            body=body,
        )
        db.add(message)
        comptes = db.query(models.User).filter(models.User.delegation_id == delegation_id).all()
        for c in comptes:
            notify(db, c.id, f"Nouveau message du BEN concernant la délégation {delegation.nom}.", link="/delegation/messagerie")
        db.commit()
    return RedirectResponse(url=f"/admin/messagerie-delegations/{delegation_id}", status_code=status.HTTP_303_SEE_OTHER)
