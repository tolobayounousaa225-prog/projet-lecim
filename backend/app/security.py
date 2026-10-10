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
    """Retourne un message d'erreur si le mot de passe ne respecte pas la politique
    minimale (longueur, présence d'au moins une lettre et un chiffre), sinon None."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Le mot de passe doit contenir au moins {PASSWORD_MIN_LENGTH} caractères."
    if not any(c.isalpha() for c in password):
        return "Le mot de passe doit contenir au moins une lettre."
    if not any(c.isdigit() for c in password):
        return "Le mot de passe doit contenir au moins un chiffre."
    return None


def generate_temp_password() -> str:
    """Mot de passe temporaire lisible (sans caractères ambigus 0/O/1/l), qui
    respecte toujours la politique minimale (lettres + chiffres)."""
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(10))
        if not password_policy_error(candidate):
            return candidate


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


TWO_FACTOR_PENDING_PURPOSE = "2fa_pending"
TWO_FACTOR_PENDING_MINUTES = 5


def generate_otp_code() -> str:
    """Code à 6 chiffres (aléatoire cryptographique, pas `random`) envoyé par
    e-mail comme second facteur de connexion."""
    return "".join(secrets.choice(string.digits) for _ in range(6))


def hash_otp_code(code: str) -> str:
    """Empreinte (HMAC, clé = SECRET_KEY) du code, jamais le code en clair —
    seule cette empreinte voyage dans le jeton `two_factor_pending`, qui lui
    n'est que *signé* (JWT), pas chiffré : son contenu reste lisible par
    quiconque détient le cookie. Y mettre le code en clair aurait permis de
    retrouver le second facteur sans jamais avoir reçu l'e-mail."""
    return hmac.new(settings.secret_key.encode(), code.strip().encode(), hashlib.sha256).hexdigest()


def create_two_factor_pending_token(subject: str, code_hash: str) -> str:
    """Jeton très courte durée prouvant que le mot de passe a déjà été vérifié,
    en attendant la saisie du code reçu par e-mail — distinct du jeton de
    session normal par sa revendication `purpose`, pour qu'il ne puisse jamais
    être accepté à la place d'un vrai jeton d'accès si on tentait de le
    présenter comme cookie `access_token`."""
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=TWO_FACTOR_PENDING_MINUTES)
    payload = {"sub": subject, "exp": expire, "purpose": TWO_FACTOR_PENDING_PURPOSE, "code_hash": code_hash}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_two_factor_pending_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
    if payload.get("purpose") != TWO_FACTOR_PENDING_PURPOSE:
        return None
    if not payload.get("sub") or not payload.get("code_hash"):
        return None
    return {"email": payload["sub"], "code_hash": payload["code_hash"]}
