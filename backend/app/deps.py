from fastapi import Cookie, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from . import models
from .database import get_db
from .security import decode_access_token


class NotAuthenticatedException(Exception):
    """Raised by web (cookie-based) routes; handled by a redirect to /admin/login."""


class NotAuthorizedException(Exception):
    """Raised by web routes when a logged-in user lacks the required access level."""


class WrongPortalException(Exception):
    """Raised when a logged-in account uses the wrong login portal (BEN vs délégation)."""

    def __init__(self, redirect_to: str):
        self.redirect_to = redirect_to


class DelegationNotAuthenticatedException(Exception):
    """Raised by délégation portal routes; handled by a redirect to /delegation/login."""


class EtablissementNotAuthenticatedException(Exception):
    """Raised by établissement portal routes; handled by a redirect to /etablissement/login."""


def _home_portal(user: "models.User") -> str:
    if user.is_delegation_account:
        return "/delegation"
    if user.is_etablissement_account:
        return "/etablissement"
    return "/admin"


def _extract_token(authorization: str | None, access_token_cookie: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1]
    return access_token_cookie


def get_current_user(
    authorization: str | None = Header(default=None),
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> models.User:
    token = _extract_token(authorization, access_token)
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentification requise",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_error

    email = decode_access_token(token)
    if not email:
        raise credentials_error

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise credentials_error
    return user


def get_current_admin(
    user: models.User = Depends(get_current_user),
) -> models.User:
    """Backward-compatible name: requires admin-level access (via API bearer token)."""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé aux administrateurs")
    return user


def require_login_web(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> models.User:
    """Any BEN account (Bureau Exécutif National) — used for pages everyone in the BEN
    portal may reach (ex: le tableau de bord). Comptes délégation exclus : ils ont leur
    propre portail sur /delegation."""
    if not access_token:
        raise NotAuthenticatedException()
    email = decode_access_token(access_token)
    if not email:
        raise NotAuthenticatedException()
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise NotAuthenticatedException()
    if user.is_delegation_account or user.is_etablissement_account:
        raise WrongPortalException(redirect_to=_home_portal(user))
    return user


def require_delegation_login_web(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> models.User:
    """Comptes délégation régionale uniquement — portail séparé du BEN."""
    if not access_token:
        raise DelegationNotAuthenticatedException()
    email = decode_access_token(access_token)
    if not email:
        raise DelegationNotAuthenticatedException()
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise DelegationNotAuthenticatedException()
    if not user.is_delegation_account:
        raise WrongPortalException(redirect_to=_home_portal(user))
    return user


def require_etablissement_login_web(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> models.User:
    """Comptes établissement uniquement — portail séparé du BEN et des délégations."""
    if not access_token:
        raise EtablissementNotAuthenticatedException()
    email = decode_access_token(access_token)
    if not email:
        raise EtablissementNotAuthenticatedException()
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise EtablissementNotAuthenticatedException()
    if not user.is_etablissement_account:
        raise WrongPortalException(redirect_to=_home_portal(user))
    return user


def _etab_module_dependency_web(module_key: str):
    """Fabrique une dépendance exigeant l'accès à une rubrique de l'espace établissement
    (titulaire : accès total ; secrétaire : uniquement les rubriques accordées)."""

    def _dependency(user: models.User = Depends(require_etablissement_login_web)) -> models.User:
        if not user.has_etab_module(module_key):
            raise NotAuthorizedException()
        return user

    return _dependency


require_etab_cotisation_web = _etab_module_dependency_web("cotisation")
require_etab_resultats_web = _etab_module_dependency_web("resultats")
require_etab_enseignants_web = _etab_module_dependency_web("enseignants")
require_etab_effectifs_web = _etab_module_dependency_web("effectifs")
require_etab_cartes_web = _etab_module_dependency_web("cartes_scolaires")
require_etab_demandes_web = _etab_module_dependency_web("demandes")
require_etab_annonces_web = _etab_module_dependency_web("annonces")
require_etab_messagerie_web = _etab_module_dependency_web("messagerie")


def require_admin_web(
    user: models.User = Depends(require_login_web),
) -> models.User:
    """Admin-level access only — used for user management and full content control."""
    if not user.is_admin:
        raise NotAuthorizedException()
    return user


def _module_dependency_web(module_key: str):
    """Fabrique une dépendance cookie-based exigeant l'accès au module donné."""

    def _dependency(user: models.User = Depends(require_login_web)) -> models.User:
        if not user.has_module(module_key):
            raise NotAuthorizedException()
        return user

    return _dependency


def _module_dependency_api(module_key: str):
    """Fabrique une dépendance API (bearer/cookie) exigeant l'accès au module donné."""

    def _dependency(user: models.User = Depends(get_current_user)) -> models.User:
        if not user.has_module(module_key):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès non autorisé")
        return user

    return _dependency


# ---------- Dépendances web (panneau admin, cookie de session) ----------
require_reunions_access_web = _module_dependency_web("reunions")
require_membres_access_web = _module_dependency_web("membres")
require_documents_access_web = _module_dependency_web("documents")
require_photos_access_web = _module_dependency_web("photos")
require_news_access_web = _module_dependency_web("news")
require_activities_access_web = _module_dependency_web("activities")
require_contact_access_web = _module_dependency_web("contact")
require_finance_access_web = _module_dependency_web("finances")
require_cartes_gestion_web = _module_dependency_web("cartes_gestion")
require_partenaires_access_web = _module_dependency_web("partenaires")
require_projets_patrimoine_access_web = _module_dependency_web("projets_patrimoine")
require_affaires_sociales_access_web = _module_dependency_web("affaires_sociales")
require_publications_access_web = _module_dependency_web("publications")
require_executif_access_web = _module_dependency_web("executif")
require_delegations_access_web = _module_dependency_web("delegations")
require_historique_access_web = _module_dependency_web("historique")
require_gouvernance_access_web = _module_dependency_web("gouvernance")
require_site_content_access_web = _module_dependency_web("site_content")
require_enseignants_access_web = _module_dependency_web("enseignants")
require_resultats_examens_access_web = _module_dependency_web("resultats_examens")
require_sondages_access_web = _module_dependency_web("sondages")
require_effectifs_access_web = _module_dependency_web("effectifs")
require_cartes_scolaires_access_web = _module_dependency_web("cartes_scolaires")
require_messagerie_access_web = _module_dependency_web("messagerie")


def require_delegation_management_web(
    user: models.User = Depends(require_login_web),
) -> models.User:
    """Créer/gérer les délégations et leurs comptes : administrateur ou 2e Vice-Président
    chargé de l'Intérieur (statutairement en charge de l'implantation de la LECIM)."""
    if user.is_admin or user.poste == "vp2_interieur":
        return user
    raise NotAuthorizedException()

# ---------- Dépendances API (JWT bearer, utilisées par /api/news et /api/activities) ----------
get_news_editor = _module_dependency_api("news")
get_activities_editor = _module_dependency_api("activities")


def get_optional_admin(
    authorization: str | None = Header(default=None),
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> models.User | None:
    token = _extract_token(authorization, access_token)
    if not token:
        return None
    email = decode_access_token(token)
    if not email:
        return None
    return db.query(models.User).filter(models.User.email == email).first()
