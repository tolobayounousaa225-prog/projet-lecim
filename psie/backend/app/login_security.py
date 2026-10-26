"""Authentification avec verrouillage anti-brute-force (même logique que la LECIM) :
un seul mécanisme, appliqué à tous les points d'entrée de connexion."""

import datetime

from sqlalchemy.orm import Session

from . import models
from .security import verify_password

MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


class AccountLockedError(Exception):
    def __init__(self, minutes_left: int):
        self.minutes_left = minutes_left
        super().__init__(f"Compte verrouillé pour encore {minutes_left} min")


def authenticate_user(db: Session, email: str, password: str) -> "models.User | None":
    """Retourne l'utilisateur si les identifiants sont corrects, None sinon (le compteur
    d'échecs est alors incrémenté et commité). Lève AccountLockedError si verrouillé."""
    user = db.query(models.User).filter(models.User.email == email.strip().lower()).first()
    now = datetime.datetime.utcnow()

    if user and user.locked_until and user.locked_until > now:
        minutes_left = max(1, int((user.locked_until - now).total_seconds() // 60) + 1)
        raise AccountLockedError(minutes_left)

    if not user or not user.is_active or not verify_password(password, user.hashed_password):
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
                user.locked_until = now + datetime.timedelta(minutes=LOCKOUT_MINUTES)
                user.failed_login_attempts = 0
            db.commit()
        return None

    user.failed_login_attempts = 0
    user.locked_until = None
    return user
