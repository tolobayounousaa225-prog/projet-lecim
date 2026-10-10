"""Vérification du code de connexion envoyé par e-mail — second facteur
obligatoire pour les comptes admin et finances (voir
`models.User.requires_two_factor`), déclenché par `admin.login_submit` entre
la vérification du mot de passe et l'octroi de la session complète."""

from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, Form, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..database import get_db
from ..deps import require_two_factor_pending
from ..email_utils import send_email
from ..rate_limit import rate_limiter
from ..security import (
    TWO_FACTOR_PENDING_MINUTES,
    create_two_factor_pending_token,
    decode_two_factor_pending_token,
    generate_otp_code,
    hash_otp_code,
)
from .admin import issue_session_cookie

router = APIRouter(prefix="/admin/2fa", tags=["admin-2fa"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/verify")
def two_factor_verify_page(
    request: Request,
    user: models.User = Depends(require_two_factor_pending),
):
    return templates.TemplateResponse(request, "admin/two_factor_verify.html", {"error": None, "message": None})


@router.post("/verify", dependencies=[Depends(rate_limiter("2fa-verify", 10, 600))])
def two_factor_verify_submit(
    request: Request,
    code: str = Form(...),
    user: models.User = Depends(require_two_factor_pending),
    two_factor_pending: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    decoded = decode_two_factor_pending_token(two_factor_pending) if two_factor_pending else None
    if not decoded or decoded["code_hash"] != hash_otp_code(code):
        return templates.TemplateResponse(
            request,
            "admin/two_factor_verify.html",
            {"error": "Code incorrect ou expiré.", "message": None},
            status_code=401,
        )
    return issue_session_cookie(user, request, db, "/admin", "ben")


@router.post("/resend", dependencies=[Depends(rate_limiter("2fa-resend", 5, 600))])
def two_factor_resend(
    request: Request,
    user: models.User = Depends(require_two_factor_pending),
):
    code = generate_otp_code()
    send_email(
        user.email,
        "LECIM — Code de vérification",
        f"Bonjour {user.full_name},\n\n"
        f"Voici votre nouveau code de connexion : {code}\n\n"
        f"Il est valable {TWO_FACTOR_PENDING_MINUTES} minutes.",
    )
    pending_token = create_two_factor_pending_token(subject=user.email, code_hash=hash_otp_code(code))
    response = templates.TemplateResponse(
        request,
        "admin/two_factor_verify.html",
        {"error": None, "message": "Un nouveau code vient de vous être envoyé par e-mail."},
    )
    response.set_cookie(
        "two_factor_pending", pending_token, httponly=True, samesite="lax",
        secure=not settings.debug,
        max_age=TWO_FACTOR_PENDING_MINUTES * 60,
    )
    return response
