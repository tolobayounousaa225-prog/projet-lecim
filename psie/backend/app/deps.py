from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from . import acces, models
from .database import get_db
from .security import decode_access_token, decode_view_as_token

VIEW_AS_COOKIE = "view_as"
# Adresses encore utilisables en mode consultation (sortir du mode, changer de langue, se déconnecter)
VIEW_AS_EXEMPT = ("/supervision/quitter", "/logout")


def _preview_user(db: Session, real: models.User, spec: str, request: Request) -> models.User:
    """Aperçu du portail d'un rôle, même si aucun compte n'existe encore : une personne virtuelle (jamais enregistrée en base)
    avec les droits du rôle. Toujours en lecture seule."""
    parts = spec.split(":")                                  # apercu:<rôle> ou apercu:faitiere:<n° de faîtière>
    role = parts[1] if len(parts) > 1 else ""
    if role not in models.ROLES or role == "admin":
        return real
    fid = None
    if role == "faitiere":
        fid = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
        fa = db.get(models.Faitiere, fid) if fid else None
        if not fa:
            return real
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.url.path not in VIEW_AS_EXEMPT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Mode consultation : lecture seule, aucune modification n'est possible. Quittez la consultation pour agir.")
    label = models.ROLES[role] + (f" — {fa.sigle}" if fid else "")
    ghost = models.User(id=-1, email=f"apercu-{role}@psie.invalid", hashed_password="!", full_name=f"Aperçu : {label}", role=role,
                        faitiere_id=fid, is_active=True)
    ghost._perms = acces.role_defaults_with_overrides(db, role)
    ghost._real = real
    return ghost


def _resolve_view_as(request: Request, db: Session, real: models.User, token: str | None) -> models.User:
    """Mode supervision : une personne habilitée (rubrique « supervision » en modification) consulte l'espace d'un autre
    compte EN LECTURE SEULE. Le jeton est signé, expire en une heure et n'est valable que pour cette personne."""
    if not token:
        return real
    data = decode_view_as_token(token)
    if not data or data[0] != real.email:
        return real
    real._perms = acces.effective(db, real)
    if not real.is_internal or real.level("supervision") < acces.ECRITURE:
        return real
    if isinstance(data[1], str):
        return _preview_user(db, real, data[1], request)
    target = db.get(models.User, data[1])
    if not target or not target.is_active or target.id == real.id or (target.is_admin and not real.is_admin):
        return real
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.url.path not in VIEW_AS_EXEMPT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Mode consultation : lecture seule, aucune modification n'est possible. Quittez la consultation pour agir.")
    target._perms = acces.effective(db, target)
    target._real = real
    return target


class NotAuthenticatedException(Exception):
    """Levée par les pages web ; transformée en redirection vers /login."""


def get_current_user(
    request: Request,
    access_token: str | None = Cookie(default=None),
    view_as: str | None = Cookie(default=None),
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
    return _resolve_view_as(request, db, user, view_as)


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
    request: Request,
    access_token: str | None = Cookie(default=None),
    view_as: str | None = Cookie(default=None),
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
    return _resolve_view_as(request, db, user, view_as)


def visibility_guard(request: Request, user: models.User | None = Depends(get_optional_user)) -> None:
    """Appliquée à toute l'application : un compte d'organe ne peut ouvrir aucune adresse d'une rubrique qui ne fait
    pas partie de son espace, même en tapant l'adresse à la main. Les représentants de faîtière ont leurs propres
    règles (ils ne voient que leur faîtière)."""
    if user is None or not user.is_internal:
        return
    path = request.url.path
    if path == "/supervision/quitter":
        return                                   # on doit toujours pouvoir quitter le mode consultation
    if acces.is_admin_only(path):
        return                                   # les gardes de ces pages exigent déjà l'administrateur
    section = acces.section_for_path(path)
    if section and user.level(section) < acces.LECTURE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cette rubrique ne fait pas partie de votre espace")
