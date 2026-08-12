import datetime

import bcrypt
from jose import JWTError, jwt

from .config import settings


PASSWORD_MIN_LENGTH = 8


def password_policy_error(password: str) -> str | None:
    """Retourne un message d'erreur si le mot de passe ne respecte pas la politique
    minimale (longueur, présence d'au moins une lettre et un chiffre), sinon None."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Le mot de passe doit contenir au moins {PASSWORD_MIN_LENGTH} caractères."
    if not any(c.isalpha() for c in password):
        return "Le mot de passe doit contenir au moins une lettre."
    if not any(c.isdigit() for c in password):
        return "Le mot de passe doit contenir au moins un chiffre."
    return None


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(subject: str) -> str:
    expire = datetime.datetime.utcnow() + datetime.timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload.get("sub")
    except JWTError:
        return None
