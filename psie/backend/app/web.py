"""Rendu des pages : contexte commun (utilisateur, langue, traduction) et petits utilitaires."""

import datetime
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates

from .config import settings
from . import models
from .i18n import label, normalize_lang, translate

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def current_lang(request: Request) -> str:
    return normalize_lang(request.cookies.get("lang"))


def render(request: Request, name: str, user: "models.User | None" = None, status_code: int = 200, **ctx):
    lang = current_lang(request)
    ctx.update(
        user=user,
        app_shell=user is not None,
        request=request,
        lang=lang,
        dir="rtl" if lang == "ar" else "ltr",
        t=lambda key: translate(key, lang),
        lbl=lambda kind, key: label(kind, key, lang),
        categories=models.CATEGORIES,
        statuts=models.STATUTS_MEMBRE,
        organes=models.ORGANES,
        roles=models.ROLES,
        vitrine_url=settings.vitrine_url.rstrip("/"),
    )
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)


def request_user(request: Request) -> "models.User | None":
    """Compte connecté d'après le cookie (pour les pages d'erreur, qui n'ont pas de dépendance de session)."""
    from .database import SessionLocal
    from . import acces
    from .security import decode_access_token

    token = request.cookies.get("access_token")
    email = decode_access_token(token) if token else None
    if not email:
        return None
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user or not user.is_active:
            return None
        user._perms = acces.effective(db, user)
        db.expunge(user)
        return user
    finally:
        db.close()


def parse_date(value: str | None) -> datetime.date | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Date invalide : {value}")


def clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None
