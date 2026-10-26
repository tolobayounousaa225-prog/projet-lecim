from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

import hmac

from .. import models
from ..audit import log_action
from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..emailing import send_email
from ..i18n import SUPPORTED_LANGS
from ..login_security import AccountLockedError, authenticate_user, register_failure
from ..security import (
    create_access_token, create_two_factor_token, decode_two_factor_token,
    generate_otp_code, hash_otp_code,
)
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
    if user.requires_two_factor and settings.two_factor_enabled:
        code = generate_otp_code()
        sent = send_email(
            user.email, "PSIE — Code de connexion",
            f"Votre code de connexion PSIE : {code}\nValable 5 minutes.\n\nرمز الدخول إلى PSIE: {code}",
        )
        if not sent:
            db.commit()
            return render(request, "login.html", status_code=503, error="login_2fa_unavailable")
        db.commit()
        response = RedirectResponse("/login/verification", status_code=303)
        _set_cookie(response, "two_factor_pending", create_two_factor_token(user.email, hash_otp_code(code)), 300)
        return response
    return _finish_login(db, user)


def _set_cookie(response, name: str, value: str, max_age: int) -> None:
    response.set_cookie(
        name, value, httponly=True, samesite="lax", secure=settings.cookie_secure, max_age=max_age,
    )


def _finish_login(db: Session, user: models.User):
    log_action(db, user, "connexion", "user", user.id)
    db.commit()
    response = RedirectResponse(home_for(user), status_code=303)
    _set_cookie(response, "access_token", create_access_token(user.email), settings.access_token_expire_minutes * 60)
    response.delete_cookie("two_factor_pending")
    return response


@router.get("/login/verification")
def two_factor_page(request: Request):
    if not request.cookies.get("two_factor_pending"):
        return RedirectResponse("/login", status_code=303)
    return render(request, "login_2fa.html")


@router.post("/login/verification")
def two_factor_verify(request: Request, code: str = Form(...), db: Session = Depends(get_db)):
    pending = decode_two_factor_token(request.cookies.get("two_factor_pending", ""))
    if not pending:
        return RedirectResponse("/login", status_code=303)
    user = db.query(models.User).filter(models.User.email == pending["email"]).first()
    if not user or not user.is_active:
        return RedirectResponse("/login", status_code=303)
    try:
        locked = register_failure(db, user, check_only=True)
    except AccountLockedError:
        return render(request, "login_2fa.html", status_code=429, error="login_locked")
    if not hmac.compare_digest(hash_otp_code(code), pending["code_hash"]):
        # Les codes faux comptent comme des échecs de connexion : verrouillage après 5 essais
        try:
            register_failure(db, user)
        except AccountLockedError:
            return render(request, "login_2fa.html", status_code=429, error="login_locked")
        return render(request, "login_2fa.html", status_code=401, error="code_error")
    user.failed_login_attempts = 0
    return _finish_login(db, user)


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
