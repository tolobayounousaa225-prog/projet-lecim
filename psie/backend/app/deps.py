from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from . import models
from .database import get_db
from .security import decode_access_token


class NotAuthenticatedException(Exception):
    """Levée par les pages web ; transformée en redirection vers /login."""


def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> models.User:
    if not access_token:
        raise NotAuthenticatedException()
    email = decode_access_token(access_token)
    if not email:
        raise NotAuthenticatedException()
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not user.is_active:
        raise NotAuthenticatedException()
    return user


def require_internal(user: models.User = Depends(get_current_user)) -> models.User:
    """Tout compte rattaché à un organe de la PSIE (pas un représentant de faîtière)."""
    if not user.is_internal:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé aux organes de la PSIE")
    return user


def require_member_manager(user: models.User = Depends(get_current_user)) -> models.User:
    if not user.can_manage_members:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action non autorisée pour votre rôle")
    return user


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Réservé à l'administrateur")
    return user
