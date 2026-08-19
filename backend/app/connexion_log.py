"""Journalisation des connexions réussies et détection d'un appareil jamais vu."""

from fastapi import Request
from sqlalchemy.orm import Session

from . import models
from .email_utils import send_email
from .notifications import notify


def record_login(db: Session, user: "models.User", request: Request) -> None:
    ip_address = request.client.host if request.client else None
    user_agent = (request.headers.get("user-agent") or "")[:500]

    has_prior_logins = (
        db.query(models.ConnexionLog).filter(models.ConnexionLog.user_id == user.id).first() is not None
    )
    # Reconnu seulement si la MÊME combinaison navigateur + adresse IP a déjà été
    # vue — un navigateur générique (Chrome/Windows) identique ne suffit plus à
    # masquer une connexion depuis une IP jamais vue pour ce compte (un simple
    # User-Agent partagé par des millions de machines n'authentifiait rien).
    known_device = (
        db.query(models.ConnexionLog)
        .filter(
            models.ConnexionLog.user_id == user.id,
            models.ConnexionLog.user_agent == user_agent,
            models.ConnexionLog.ip_address == ip_address,
        )
        .first()
        is not None
    )
    is_new_device = has_prior_logins and not known_device

    db.add(
        models.ConnexionLog(
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent or None,
            is_new_device=is_new_device,
        )
    )

    if is_new_device:
        home_link = "/delegation" if user.is_delegation_account else "/etablissement" if user.is_etablissement_account else "/admin"
        message = (
            f"Nouvelle connexion depuis un appareil non reconnu (IP {ip_address or 'inconnue'})."
        )
        notify(db, user.id, message, link=home_link)
        send_email(
            user.email,
            "LECIM — Connexion depuis un nouvel appareil",
            f"Bonjour {user.full_name},\n\n"
            f"Une connexion à votre compte LECIM vient d'avoir lieu depuis un appareil ou "
            f"navigateur que nous n'avons jamais vu pour vous.\n\n"
            f"Adresse IP : {ip_address or 'inconnue'}\n"
            f"Navigateur : {user_agent or 'inconnu'}\n\n"
            f"Si ce n'est pas vous, changez votre mot de passe et contactez le secrétariat "
            f"administratif de la LECIM au plus vite.",
        )
