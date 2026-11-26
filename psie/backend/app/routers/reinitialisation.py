"""Mot de passe oublié : demande par e-mail, puis choix d'un nouveau mot de passe par lien à usage unique."""

import datetime
import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import models, password_reset
from ..audit import log_action
from ..config import settings
from ..database import get_db
from ..emailing import send_email
from ..rate_limit import rate_limiter
from ..security import hash_password, password_policy_error
from ..web import render

router = APIRouter()
logger = logging.getLogger("psie.reset")
forgot_limit = rate_limiter("mdp-oublie", 5, 3600)


@router.get("/mot-de-passe-oublie")
def forgot_page(request: Request):
    return render(request, "mdp_oublie.html")


@router.post("/mot-de-passe-oublie", dependencies=[Depends(forgot_limit)])
def forgot_submit(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    """Réponse identique que le compte existe ou non : on ne révèle jamais quelles adresses sont inscrites."""
    user = db.query(models.User).filter(models.User.email == email.strip().lower()).first()
    if user and user.is_active:
        token = password_reset.issue(db, user)
        if token:
            link = f"{settings.public_base_url.rstrip('/')}/mot-de-passe-oublie/{token}"
            sent = send_email(
                user.email, "PSIE — Réinitialisation du mot de passe",
                f"Pour choisir un nouveau mot de passe, ouvrez ce lien (valable 1 heure, à usage unique) :\n{link}\n\n"
                "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message : votre mot de passe reste inchangé.\n\n"
                f"لاختيار كلمة مرور جديدة افتحوا هذا الرابط (صالح لمدة ساعة ولمرة واحدة):\n{link}\n"
                "إذا لم تطلبوا ذلك فتجاهلوا هذه الرسالة.",
            )
            if not sent:
                logger.warning("Lien de réinitialisation non envoyé (e-mail indisponible)")
            log_action(db, user, "demande_reinit_mdp", "user", user.id)
        db.commit()
    return render(request, "mdp_oublie.html", sent=True)


@router.get("/mot-de-passe-oublie/{token}")
def reset_page(token: str, request: Request, db: Session = Depends(get_db)):
    if not password_reset.find_valid(db, token):
        return render(request, "mdp_reinit.html", status_code=400, invalid=True)
    return render(request, "mdp_reinit.html", token=token)


@router.post("/mot-de-passe-oublie/{token}")
def reset_submit(token: str, request: Request, new: str = Form(...), confirm: str = Form(...),
                 db: Session = Depends(get_db)):
    row = password_reset.find_valid(db, token)
    if not row:
        return render(request, "mdp_reinit.html", status_code=400, invalid=True)
    if new != confirm:
        return render(request, "mdp_reinit.html", status_code=400, token=token, error="password_mismatch")
    policy = password_policy_error(new)
    if policy:
        return render(request, "mdp_reinit.html", status_code=400, token=token, error_text=policy)
    user = db.get(models.User, row.user_id)
    user.hashed_password = hash_password(new)
    user.failed_login_attempts = 0
    user.locked_until = None
    # Les autres liens encore ouverts de ce compte sont supprimés ; celui-ci est marqué utilisé (jamais rejouable).
    db.query(models.ReinitialisationMdp).filter(models.ReinitialisationMdp.user_id == user.id,
                                                models.ReinitialisationMdp.id != row.id).delete(synchronize_session=False)
    row.used_at = datetime.datetime.utcnow()
    log_action(db, user, "reinitialisation_mdp", "user", user.id)
    db.commit()
    return RedirectResponse("/login?reinit=1", status_code=303)
