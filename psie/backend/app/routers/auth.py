from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import models
from ..audit import log_action
from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..i18n import SUPPORTED_LANGS
from ..login_security import AccountLockedError, authenticate_user
from ..security import create_access_token
from ..web import render

router = APIRouter()


def home_for(user: models.User) -> str:
    return "/admin" if user.is_internal else "/portail"


@router.get("/")
def index():
    return RedirectResponse("/login", status_code=303)


@router.get("/login")
def login_page(request: Request):
    return render(request, "login.html")


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    try:
        user = authenticate_user(db, email, password)
    except AccountLockedError:
        return render(request, "login.html", status_code=429, error="login_locked")
    if not user:
        return render(request, "login.html", status_code=401, error="login_error")
    log_action(db, user, "connexion", "user", user.id)
    db.commit()
    response = RedirectResponse(home_for(user), status_code=303)
    response.set_cookie(
        "access_token",
        create_access_token(user.email),
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.access_token_expire_minutes * 60,
    )
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("access_token")
    return response


@router.get("/lang/{code}")
def set_lang(code: str, request: Request):
    if code not in SUPPORTED_LANGS:
        code = "fr"
    back = request.headers.get("referer") or "/"
    # Redirection uniquement vers le même site (évite une redirection ouverte via Referer)
    if not back.startswith(str(request.base_url)):
        back = "/"
    response = RedirectResponse(back, status_code=303)
    response.set_cookie("lang", code, max_age=365 * 24 * 3600, samesite="lax")
    return response


@router.get("/portail")
def portail(request: Request, user: models.User = Depends(get_current_user)):
    """Espace d'un représentant de faîtière : sa propre fiche uniquement."""
    if user.is_internal:
        return RedirectResponse("/admin", status_code=303)
    if not user.faitiere_id:
        return render(request, "portail_vide.html", user)
    return RedirectResponse(f"/faitieres/{user.faitiere_id}", status_code=303)
