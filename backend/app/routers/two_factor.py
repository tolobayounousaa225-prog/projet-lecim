"""Inscription et vérification de la double authentification (TOTP) — second
facteur obligatoire pour les comptes admin et finances (voir
`models.User.requires_two_factor`), déclenché par `admin.login_submit` entre
la vérification du mot de passe et l'octroi de la session complète."""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_two_factor_pending
from ..rate_limit import rate_limiter
from ..totp import build_qr_code_data_uri, generate_secret, verify_code
from .admin import issue_session_cookie

router = APIRouter(prefix="/admin/2fa", tags=["admin-2fa"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/enroll")
def two_factor_enroll_page(
    request: Request,
    user: models.User = Depends(require_two_factor_pending),
    db: Session = Depends(get_db),
):
    if user.totp_enabled:
        return issue_session_cookie(user, request, db, "/admin", "ben")
    if not user.totp_secret:
        user.totp_secret = generate_secret()
        db.commit()
    return templates.TemplateResponse(
        request,
        "admin/two_factor_enroll.html",
        {
            "error": None,
            "secret": user.totp_secret,
            "qr_code_data_uri": build_qr_code_data_uri(user.totp_secret, user.email),
        },
    )


@router.post("/enroll", dependencies=[Depends(rate_limiter("2fa-enroll", 10, 600))])
def two_factor_enroll_submit(
    request: Request,
    code: str = Form(...),
    user: models.User = Depends(require_two_factor_pending),
    db: Session = Depends(get_db),
):
    if not user.totp_secret or not verify_code(user.totp_secret, code):
        return templates.TemplateResponse(
            request,
            "admin/two_factor_enroll.html",
            {
                "error": "Code incorrect — vérifiez l'heure de votre téléphone et réessayez.",
                "secret": user.totp_secret,
                "qr_code_data_uri": build_qr_code_data_uri(user.totp_secret, user.email),
            },
            status_code=401,
        )
    user.totp_enabled = True
    db.commit()
    return issue_session_cookie(user, request, db, "/admin", "ben")


@router.get("/verify")
def two_factor_verify_page(
    request: Request,
    user: models.User = Depends(require_two_factor_pending),
):
    return templates.TemplateResponse(request, "admin/two_factor_verify.html", {"error": None})


@router.post("/verify", dependencies=[Depends(rate_limiter("2fa-verify", 10, 600))])
def two_factor_verify_submit(
    request: Request,
    code: str = Form(...),
    user: models.User = Depends(require_two_factor_pending),
    db: Session = Depends(get_db),
):
    if not user.totp_secret or not verify_code(user.totp_secret, code):
        return templates.TemplateResponse(
            request,
            "admin/two_factor_verify.html",
            {"error": "Code incorrect."},
            status_code=401,
        )
    return issue_session_cookie(user, request, db, "/admin", "ben")
