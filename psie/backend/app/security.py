import datetime
import hashlib
import hmac
import secrets
import string

import bcrypt
from jose import JWTError, jwt

from .config import settings

PASSWORD_MIN_LENGTH = 8


def password_policy_error(password: str) -> str | None:
    """Message d'erreur si le mot de passe est trop faible, sinon None."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Le mot de passe doit contenir au moins {PASSWORD_MIN_LENGTH} caractères."
    if not any(c.isalpha() for c in password):
        return "Le mot de passe doit contenir au moins une lettre."
    if not any(c.isdigit() for c in password):
        return "Le mot de passe doit contenir au moins un chiffre."
    return None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(subject: str) -> str:
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": subject, "exp": expire}, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
    # Un jeton à usage spécifique (ex. attente du code de double authentification) ne doit
    # jamais ouvrir une session : seuls les jetons d'accès, sans `purpose`, sont acceptés.
    if payload.get("purpose"):
        return None
    return payload.get("sub")


# ---------- Double authentification par e-mail ----------

TWO_FACTOR_PURPOSE = "2fa_pending"
TWO_FACTOR_MINUTES = 5


def generate_otp_code() -> str:
    """Code à 6 chiffres (aléatoire cryptographique)."""
    return "".join(secrets.choice(string.digits) for _ in range(6))


def hash_otp_code(code: str) -> str:
    """Empreinte HMAC du code : seule cette empreinte voyage dans le jeton, jamais le code
    (le jeton est signé mais lisible)."""
    return hmac.new(settings.secret_key.encode(), code.strip().encode(), hashlib.sha256).hexdigest()


def create_two_factor_token(subject: str, code_hash: str) -> str:
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=TWO_FACTOR_MINUTES)
    payload = {"sub": subject, "exp": expire, "purpose": TWO_FACTOR_PURPOSE, "code_hash": code_hash}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_two_factor_token(token: str) -> dict | None:
    """Le jeton `access_token` normal n'est jamais accepté ici (revendication `purpose`)."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
    if payload.get("purpose") != TWO_FACTOR_PURPOSE or not payload.get("sub") or not payload.get("code_hash"):
        return None
    return {"email": payload["sub"], "code_hash": payload["code_hash"]}
