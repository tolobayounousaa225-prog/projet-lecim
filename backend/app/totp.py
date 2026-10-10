"""Double authentification (TOTP, type Google Authenticator / Authy) — code à
usage unique dérivé d'un secret partagé et de l'heure courante, indépendant du
mot de passe. Obligatoire pour les comptes admin et finances (voir
`models.User.requires_two_factor`) : un seul mot de passe compromis (phishing,
réutilisation) ne suffit alors plus à usurper un compte à fort privilège."""

import base64
import io

import pyotp
import qrcode

ISSUER_NAME = "LECIM"


def generate_secret() -> str:
    return pyotp.random_base32()


def build_provisioning_uri(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER_NAME)


def build_qr_code_data_uri(secret: str, email: str) -> str:
    """PNG encodé en base64, directement utilisable comme `src` d'une balise
    <img> — évite d'avoir à stocker ou servir un fichier image temporaire pour
    un secret qui ne doit jamais toucher le disque ou une table de fichiers."""
    uri = build_provisioning_uri(secret, email)
    img = qrcode.make(uri)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def verify_code(secret: str, code: str) -> bool:
    # valid_window=1 : tolère un léger décalage d'horloge entre le serveur et
    # le téléphone (une période de 30s avant/après), sans élargir davantage la
    # fenêtre d'attaque par essais successifs (déjà limitée par le rate-limiter
    # sur les routes de vérification).
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)
