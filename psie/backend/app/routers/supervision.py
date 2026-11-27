"""Supervision : voir ce que font les comptes et consulter leur espace EN LECTURE SEULE.

Rubrique « supervision » de la grille d'accès (administrateur et DEN par défaut) :
  lecture      -> liste des comptes et activité de chacun ;
  modification -> en plus, « voir l'espace » d'un compte : on voit exactement ce qu'il voit, sans rien pouvoir modifier.
Chaque consultation est inscrite au journal d'audit (action sensible) et signalée à l'administrateur."""

import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import acces, audit, models
from ..audit import log_action
from ..database import get_db
from ..deps import VIEW_AS_COOKIE, get_current_user
from ..security import create_view_as_token, VIEW_AS_MINUTES
from ..config import settings
from ..web import render

router = APIRouter()


def _need(user: models.User, write: bool = False) -> None:
    if user.supervisor is not None:
        raise HTTPException(status_code=403, detail="Quittez d'abord le mode consultation")
    if not user.is_internal or not user.can("supervision", write):
        raise HTTPException(status_code=403, detail="Cette rubrique ne fait pas partie de votre espace")


def _can_view_as(real: models.User, target: models.User) -> bool:
    return real.can("supervision", True) and target.id != real.id and target.is_active and (real.is_admin or not target.is_admin)


@router.get("/supervision")
def supervision_page(request: Request, role: str = "", q: str = "", user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    _need(user)
    now = datetime.datetime.utcnow()
    week = now - datetime.timedelta(days=7)
    query = db.query(models.User).order_by(models.User.role, models.User.full_name)
    if role in models.ROLES:
        query = query.filter_by(role=role)
    if q.strip():
        like = f"%{q.strip()[:60]}%"
        query = query.filter(models.User.full_name.ilike(like) | models.User.email.ilike(like))
    people = query.all()
    last_login = dict(db.query(models.AuditLog.user_id, func.max(models.AuditLog.created_at)).filter(models.AuditLog.action == "connexion")
                      .group_by(models.AuditLog.user_id))
    last_action = dict(db.query(models.AuditLog.user_id, func.max(models.AuditLog.created_at)).filter(models.AuditLog.action != "connexion")
                       .group_by(models.AuditLog.user_id))
    weekly = dict(db.query(models.AuditLog.user_id, func.count(models.AuditLog.id)).filter(models.AuditLog.created_at >= week,
                                                                                            models.AuditLog.action != "connexion").group_by(models.AuditLog.user_id))
    rows = [{"u": p, "login": last_login.get(p.id), "action": last_action.get(p.id), "week": weekly.get(p.id, 0), "can_view": _can_view_as(user, p)}
            for p in people]
    return render(request, "supervision.html", user, rows=rows, role=role, q=q, roles=models.ROLES, now=now,
                  can_view_as=user.can("supervision", True))


@router.get("/supervision/{user_id}/activite")
def activity_page(user_id: int, request: Request, debut: str = "", fin: str = "", page: int = 1,
                  user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _need(user)
    target = db.get(models.User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    query = db.query(models.AuditLog).filter(models.AuditLog.user_id == target.id)
    try:
        if debut:
            query = query.filter(models.AuditLog.created_at >= datetime.datetime.combine(datetime.date.fromisoformat(debut), datetime.time.min))
        if fin:
            query = query.filter(models.AuditLog.created_at <= datetime.datetime.combine(datetime.date.fromisoformat(fin), datetime.time.max))
    except ValueError:
        pass
    total = query.count()
    pages = max(1, -(-total // audit.PAGE_SIZE))
    page = min(max(page, 1), pages)
    entries = query.order_by(models.AuditLog.id.desc()).offset((page - 1) * audit.PAGE_SIZE).limit(audit.PAGE_SIZE).all()
    month = datetime.datetime.utcnow() - datetime.timedelta(days=30)
    summary = (db.query(models.AuditLog.entity, func.count(models.AuditLog.id))
               .filter(models.AuditLog.user_id == target.id, models.AuditLog.created_at >= month, models.AuditLog.action != "connexion")
               .group_by(models.AuditLog.entity).order_by(func.count(models.AuditLog.id).desc()).all())
    logins = db.query(models.AuditLog).filter_by(user_id=target.id, action="connexion").order_by(models.AuditLog.id.desc()).limit(5).all()
    return render(request, "supervision_activite.html", user, target=target, entries=entries, total=total, page=page, pages=pages,
                  summary=summary, logins=logins, debut=debut, fin=fin, can_view=_can_view_as(user, target), is_sensitive=audit.is_sensitive)


@router.post("/supervision/{user_id}/voir")
def view_as(user_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _need(user, write=True)
    target = db.get(models.User, user_id)
    if not target or not _can_view_as(user, target):
        raise HTTPException(status_code=403, detail="Ce compte ne peut pas être consulté")
    log_action(db, user, "consultation_compte", "user", target.id, f"{target.email} ({target.role})")
    db.commit()
    response = RedirectResponse("/admin" if target.is_internal else "/portail", status_code=303)
    response.set_cookie(VIEW_AS_COOKIE, create_view_as_token(user.email, target.id), httponly=True, samesite="lax",
                        secure=settings.cookie_secure, max_age=VIEW_AS_MINUTES * 60)
    return response


@router.post("/supervision/quitter")
def leave_view():
    response = RedirectResponse("/supervision", status_code=303)
    response.delete_cookie(VIEW_AS_COOKIE)
    return response
