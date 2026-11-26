from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from . import acces, models
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
    user._perms = acces.effective(db, user)
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


def require_write(section: str):
    """Garde d'écriture pour une rubrique (modifier, créer, supprimer)."""
    def dependency(user: models.User = Depends(get_current_user)) -> models.User:
        if not user.can(section, write=True):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action non autorisée pour votre rôle")
        return user
    return dependency


require_adhesions_write = require_write("adhesions")
require_assemblees_write = require_write("assemblees")
require_sanctions_write = require_write("sanctions")


def require_content_editor(user: models.User = Depends(get_current_user)) -> models.User:
    if not user.can_edit_site_content:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Réservé au Secrétariat Information et Communication et à l'administrateur")
    return user


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Réservé à l'administrateur")
    return user


def get_optional_user(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> models.User | None:
    """Utilisateur connecté s'il y en a un (pages publiques qui adaptent leur menu)."""
    if not access_token:
        return None
    email = decode_access_token(access_token)
    if not email:
        return None
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not user.is_active:
        return None
    user._perms = acces.effective(db, user)
    return user


def visibility_guard(request: Request, user: models.User | None = Depends(get_optional_user)) -> None:
    """Appliquée à toute l'application : un compte d'organe ne peut ouvrir aucune adresse d'une rubrique qui ne fait
    pas partie de son espace, même en tapant l'adresse à la main. Les représentants de faîtière ont leurs propres
    règles (ils ne voient que leur faîtière)."""
    if user is None or not user.is_internal:
        return
    path = request.url.path
    if acces.is_admin_only(path):
        return                                   # les gardes de ces pages exigent déjà l'administrateur
    section = acces.section_for_path(path)
    if section and user.level(section) < acces.LECTURE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cette rubrique ne fait pas partie de votre espace")
