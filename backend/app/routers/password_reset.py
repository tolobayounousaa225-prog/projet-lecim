"""Mot de passe oublié — génère un mot de passe temporaire, l'envoie par e-mail,
et le conserve en secours (visible par l'admin) tant qu'il n'a pas été utilisé."""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import audit, models
from ..database import get_db
from ..email_utils import send_email
from ..rate_limit import rate_limiter
from ..security import generate_temp_password, hash_password

router = APIRouter(tags=["password-reset"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

CONFIRMATION_MESSAGE = (
    "Si un compte existe avec cette adresse e-mail, un mot de passe temporaire vient "
    "de lui être envoyé. Vérifiez votre boîte de réception (et vos courriers indésirables)."
)


@router.get("/mot-de-passe-oublie")
def password_reset_request_page(request: Request):
    return templates.TemplateResponse(request, "password_reset_request.html", {"message": None, "error": None})


@router.post("/mot-de-passe-oublie", dependencies=[Depends(rate_limiter("password-reset", 5, 900))])
def password_reset_request_submit(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        temp_password = generate_temp_password()
        user.hashed_password = hash_password(temp_password)
        user.failed_login_attempts = 0
        user.locked_until = None
        email_sent = send_email(
            user.email,
            "LECIM — Mot de passe temporaire",
            f"Bonjour {user.full_name},\n\n"
            f"Un mot de passe temporaire a été généré pour votre compte LECIM à votre demande "
            f"(ou celle de quelqu'un connaissant votre adresse e-mail) :\n\n"
            f"    {temp_password}\n\n"
            f"Connectez-vous avec ce mot de passe puis changez-le immédiatement depuis votre "
            f"espace personnel, rubrique « Changer mon mot de passe ».\n\n"
            f"Si vous n'êtes pas à l'origine de cette demande, contactez sans tarder le "
            f"secrétariat administratif de la LECIM.",
        )
        db.add(
            models.PasswordResetRequest(
                user_id=user.id,
                temp_password=temp_password,
                email_sent=email_sent,
            )
        )
        audit.log(
            db, None, "update", "Mot de passe", user.id,
            f"Mot de passe temporaire généré pour {user.full_name} ({user.email})"
            + ("" if email_sent else " — e-mail NON envoyé (SMTP non configuré ?), voir /admin/reinitialisations"),
        )
        db.commit()
    return templates.TemplateResponse(request, "password_reset_request.html", {"message": CONFIRMATION_MESSAGE, "error": None})
