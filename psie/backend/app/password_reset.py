"""« Mot de passe oublié » : jetons à usage unique, valables une heure, conservés sous forme d'empreinte."""

import datetime
import hashlib
import secrets

from sqlalchemy.orm import Session

from . import models

TOKEN_MINUTES = 60
INVITATION_MINUTES = 7 * 24 * 60   # lien d'invitation d'un nouveau compte : une semaine
COOLDOWN_MINUTES = 2          # pas de nouveau message pendant ce délai (évite d'inonder une boîte mail)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue(db: Session, user: models.User, minutes: int = TOKEN_MINUTES) -> str | None:
    """Crée un jeton pour ce compte et retourne sa valeur (à envoyer par e-mail), ou None si un
    message vient d'être envoyé. Les anciens jetons non utilisés sont supprimés."""
    now = datetime.datetime.utcnow()
    recent = (db.query(models.ReinitialisationMdp)
              .filter(models.ReinitialisationMdp.user_id == user.id,
                      models.ReinitialisationMdp.created_at > now - datetime.timedelta(minutes=COOLDOWN_MINUTES)).first())
    if recent:
        return None
    db.query(models.ReinitialisationMdp).filter_by(user_id=user.id, used_at=None).delete()
    token = secrets.token_urlsafe(32)
    db.add(models.ReinitialisationMdp(user_id=user.id, token_hash=hash_token(token),
                                      expires_at=now + datetime.timedelta(minutes=minutes)))
    db.flush()
    return token


def find_valid(db: Session, token: str) -> models.ReinitialisationMdp | None:
    row = db.query(models.ReinitialisationMdp).filter_by(token_hash=hash_token(token)).first()
    if not row or row.used_at is not None or row.expires_at < datetime.datetime.utcnow():
        return None
    user = db.get(models.User, row.user_id)
    return row if user and user.is_active else None
