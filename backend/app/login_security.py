"""Authentification avec verrouillage anti-brute-force, partagée entre tous les
points d'entrée de connexion (portail web /admin/login et API /api/auth/token) —
un seul mécanisme de verrouillage, appliqué partout, pour éviter qu'un endpoint
oublié ne devienne un contournement de la protection."""

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
    """Vérifie les identifiants avec verrouillage après plusieurs échecs.
    Lève AccountLockedError si le compte est actuellement verrouillé.
    Retourne None si les identifiants sont incorrects (le compteur d'échecs est
    alors incrémenté et commité immédiatement), sinon l'utilisateur authentifié
    (compteur réinitialisé en mémoire — au caller de committer)."""
    user = db.query(models.User).filter(models.User.email == email).first()

    if user and user.locked_until and user.locked_until > datetime.datetime.utcnow():
        minutes_left = max(1, int((user.locked_until - datetime.datetime.utcnow()).total_seconds() // 60) + 1)
        raise AccountLockedError(minutes_left)

    if not user or not verify_password(password, user.hashed_password):
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
                user.locked_until = datetime.datetime.utcnow() + datetime.timedelta(minutes=LOCKOUT_MINUTES)
                user.failed_login_attempts = 0
            db.commit()
        return None

    user.failed_login_attempts = 0
    user.locked_until = None
    return user
