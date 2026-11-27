"""Scellement cryptographique des PDF officiels (diplomes, attestations, cartes) —
au-dela de la signature scannee du president (purement visuelle), une vraie
signature numerique PDF (PKCS#7, embarquee dans le fichier) rend toute
modification du document detectable par n'importe quel lecteur PDF standard
(Adobe Acrobat, Chrome...), pas seulement par une inspection visuelle.

La cle privee et le certificat auto-signe LECIM sont des fichiers prives (comme
signature_president.png) : jamais commites, deployes directement sur le VPS.
Si absents (ex. environnement de developpement local), la signature est
silencieusement ignoree — le document reste valide, simplement non scelle."""

from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from fpdf import FPDF

PDF_SIGNING_KEY_PATH = Path(__file__).resolve().parent / "private_assets" / "pdf_signing_key.pem"
PDF_SIGNING_CERT_PATH = Path(__file__).resolve().parent / "private_assets" / "pdf_signing_cert.pem"

_cached_key = None
_cached_cert = None
_load_attempted = False


def _load_signing_materials():
    global _cached_key, _cached_cert, _load_attempted
    if _load_attempted:
        return _cached_key, _cached_cert
    _load_attempted = True
    if not PDF_SIGNING_KEY_PATH.exists() or not PDF_SIGNING_CERT_PATH.exists():
        return None, None
    _cached_key = serialization.load_pem_private_key(PDF_SIGNING_KEY_PATH.read_bytes(), password=None)
    _cached_cert = x509.load_pem_x509_certificate(PDF_SIGNING_CERT_PATH.read_bytes())
    return _cached_key, _cached_cert


def sign_official_pdf(pdf: FPDF, reason: str) -> bool:
    """Signe numeriquement le PDF en cours de construction juste avant son
    export (doit etre appele avant `pdf.output()`). Retourne True si la
    signature a bien ete appliquee, False si les materiaux de signature sont
    absents (environnement sans les fichiers prives)."""
    key, cert = _load_signing_materials()
    if not key or not cert:
        return False
    pdf.sign(
        key=key,
        cert=cert,
        reason=reason,
        contact_info="lecimnational@gmail.com",
        location="Abidjan, Cote d'Ivoire",
    )
    return True
