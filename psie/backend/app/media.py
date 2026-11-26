"""Fichiers déposés pour le site vitrine : on ne garde jamais le fichier tel quel.

Les images sont rouvertes et réenregistrées (suppression des métadonnées GPS/appareil, des données
cachées et de tout contenu qui ne serait pas une vraie image). Les PDF sont vérifiés à l'en-tête.
Le SVG est refusé : il peut contenir du code actif.
"""

import hashlib
import io
import re
import unicodedata

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_PDF_BYTES = 15 * 1024 * 1024
MAX_PIXELS = 40_000_000          # protège contre les images « bombes »
MAX_SIDE = 2400                  # assez grand pour tout écran, assez léger pour le site
IMAGE_FORMATS = {"JPEG": ("image/jpeg", "jpg"), "PNG": ("image/png", "png"), "WEBP": ("image/webp", "webp")}


class MediaError(ValueError):
    """Fichier refusé : le message est affiché tel quel à l'éditeur."""


def safe_name(filename: str | None) -> str:
    """Nom d'affichage sans chemin ni caractère étrange (jamais utilisé comme chemin de fichier)."""
    base = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-.")[:100]
    return base or "fichier"


def clean_image(raw: bytes) -> tuple[bytes, str, str]:
    if len(raw) > MAX_IMAGE_BYTES:
        raise MediaError("Image trop lourde (8 Mo au maximum).")
    try:
        probe = Image.open(io.BytesIO(raw))
        fmt = probe.format
        if fmt not in IMAGE_FORMATS:
            raise MediaError("Format d'image refusé : utilisez JPG, PNG ou WebP.")
        if probe.width * probe.height > MAX_PIXELS:
            raise MediaError("Image trop grande (dimensions excessives).")
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))      # respecte l'orientation des photos
        img.load()
    except MediaError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise MediaError("Ce fichier n'est pas une image valide.")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    if fmt == "JPEG":
        img.convert("RGB").save(out, "JPEG", quality=85, optimize=True)
    elif fmt == "PNG":
        img.save(out, "PNG", optimize=True)
    else:
        img.save(out, "WEBP", quality=85)
    mime, ext = IMAGE_FORMATS[fmt]
    return out.getvalue(), mime, ext


def clean_pdf(raw: bytes) -> tuple[bytes, str, str]:
    if len(raw) > MAX_PDF_BYTES:
        raise MediaError("PDF trop lourd (15 Mo au maximum).")
    if not raw.startswith(b"%PDF-"):
        raise MediaError("Ce fichier n'est pas un PDF valide.")
    return raw, "application/pdf", "pdf"


def process(raw: bytes, kind: str) -> tuple[bytes, str, str, str]:
    """Retourne (contenu nettoyé, type MIME, extension, empreinte SHA-256). kind : « image » ou « pdf »."""
    if not raw:
        raise MediaError("Fichier vide.")
    data, mime, ext = clean_image(raw) if kind == "image" else clean_pdf(raw)
    return data, mime, ext, hashlib.sha256(data).hexdigest()
