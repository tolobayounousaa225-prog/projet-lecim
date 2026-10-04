"""Jetons JWT pour la visioconférence interne (Jitsi Meet auto-hébergé sur
visio.213-199-37-74.sslip.io, voir deploy/jitsi-meet/ sur le serveur). Le serveur Jitsi
est configuré en ENABLE_GUESTS=0 + AUTH_TYPE=jwt : personne ne peut rejoindre un salon
sans un jeton signé avec le même secret que celui défini côté Jitsi
(JWT_APP_SECRET == settings.jitsi_app_secret). Chaque jeton est limité à un seul salon
et expire vite, pour qu'un lien de réunion ne reste pas valable indéfiniment."""

import datetime
import re

from jose import jwt

from .config import settings

TOKEN_VALIDITY_HOURS = 6


def jitsi_room_name(reunion_id: int) -> str:
    return f"lecim-reunion-{reunion_id}"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "membre"


def generate_jitsi_token(room: str, user_name: str, user_email: str | None, moderator: bool) -> str:
    now = datetime.datetime.utcnow()
    payload = {
        "aud": settings.jitsi_app_id,
        "iss": settings.jitsi_app_id,
        "sub": "*",
        "room": room,
        "iat": now,
        "nbf": now,
        "exp": now + datetime.timedelta(hours=TOKEN_VALIDITY_HOURS),
        "context": {
            "user": {
                "name": user_name,
                "email": user_email or "",
                "id": _slug(user_name),
                "moderator": moderator,
            }
        },
    }
    return jwt.encode(payload, settings.jitsi_app_secret, algorithm="HS256")
