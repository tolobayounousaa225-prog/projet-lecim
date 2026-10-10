"""Authentification avec verrouillage anti-brute-force, partagée entre tous les
points d'entrée de connexion (portail web /admin/login et API /api/auth/token) —
un seul mécanisme de verrouillage, appliqué partout, pour éviter qu'un endpoint
oublié ne devienne un contournement de la protection."""

import datetime
import threading

from sqlalchemy.orm import Session

from . import models
from .config import settings
from .email_utils import send_email
from .security import verify_password

MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

# Alerte par e-mail au-delà d'un volume anormal d'échecs de connexion tous
# comptes confondus (signe d'une attaque en cours — password spraying ou
# brute-force distribué — plutôt qu'un simple oubli de mot de passe isolé) :
# le rate-limiter par IP ralentit déjà l'attaquant, mais ne prévient personne.
ALERT_THRESHOLD = 30
ALERT_WINDOW_MINUTES = 60
ALERT_DEBOUNCE_MINUTES = 60

_alert_lock = threading.Lock()
_failed_attempts_window: list[datetime.datetime] = []
_last_alert_sent: datetime.datetime | None = None


def _maybe_alert_on_failed_attempts() -> None:
    global _last_alert_sent
    now = datetime.datetime.utcnow()
    cutoff = now - datetime.timedelta(minutes=ALERT_WINDOW_MINUTES)
    with _alert_lock:
        _failed_attempts_window.append(now)
        while _failed_attempts_window and _failed_attempts_window[0] < cutoff:
            _failed_attempts_window.pop(0)
        count = len(_failed_attempts_window)
        if count < ALERT_THRESHOLD:
            return
        if _last_alert_sent and (now - _last_alert_sent) < datetime.timedelta(minutes=ALERT_DEBOUNCE_MINUTES):
            return
        _last_alert_sent = now
    if settings.contact_notify_email:
        send_email(
            settings.contact_notify_email,
            "LECIM — Activité de connexion anormale détectée",
            f"{count} tentatives de connexion échouées (tous comptes confondus) ont été "
            f"enregistrées au cours des {ALERT_WINDOW_MINUTES} dernières minutes sur la "
            f"plateforme LECIM — volume inhabituel, possible tentative d'intrusion "
            f"(force brute ou essai de mots de passe sur plusieurs comptes).\n\n"
            f"Le blocage par IP et le verrouillage par compte sont déjà actifs automatiquement. "
            f"Cette alerte ne se répètera pas avant {ALERT_DEBOUNCE_MINUTES} minutes.",
        )


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
    # Verrou de ligne : deux tentatives concurrentes sur le même compte (script de
    # brute-force parallélisé, ou simplement deux onglets) ne doivent jamais
    # s'écraser mutuellement sur le compteur d'échecs, au risque de retarder ou
    # d'empêcher le verrouillage après MAX_FAILED_LOGIN_ATTEMPTS.
    user = db.query(models.User).filter(models.User.email == email).with_for_update().first()

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
        _maybe_alert_on_failed_attempts()
        return None

    user.failed_login_attempts = 0
    user.locked_until = None
    return user
