"""Stockage des fichiers uploadés (photos, documents, logos...) en base de
données plutôt que sur le disque du conteneur — voir `StoredFile` dans
models.py pour le contexte. Remplace l'ancien `_save_upload()` qui écrivait
sur `UPLOAD_ROOT`, un disque éphémère réinitialisé à chaque déploiement
(ce qui faisait perdre tous les fichiers uploadés, incident du 2026-08-20)."""

import mimetypes
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from . import models
from .config import settings

ALLOWED_DOCUMENT_EXT = {".pdf", ".doc", ".docx", ".odt"}
ALLOWED_PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_UPLOAD_BYTES = settings.max_upload_size_mb * 1024 * 1024

# Signatures binaires (magic bytes) attendues pour chaque extension autorisée —
# défense en profondeur en plus du contrôle d'extension : empêche de stocker un
# contenu arbitraire simplement renommé avec une extension permise. .docx/.odt
# sont tous deux des archives ZIP (OOXML/ODF) et partagent donc la même
# signature ; .doc (binaire historique) utilise le format OLE Compound File.
_MAGIC_BYTES: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".webp": (b"RIFF",),  # "WEBP" suit à l'offset 8, vérifié séparément ci-dessous
    ".docx": (b"PK\x03\x04",),
    ".odt": (b"PK\x03\x04",),
    ".doc": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
}


def _matches_magic_bytes(data: bytes, ext: str) -> bool:
    signatures = _MAGIC_BYTES.get(ext)
    if not signatures:
        return True  # extension sans signature connue : pas de vérification possible
    if not any(data.startswith(sig) for sig in signatures):
        return False
    if ext == ".webp" and data[8:12] != b"WEBP":
        return False
    return True


async def save_upload(db: Session, file: UploadFile | None, category: str, allowed_ext: set[str]) -> tuple[str, str]:
    """Enregistre un fichier uploadé en base de données. Retourne
    (nom_stocke, nom_original) — le nom stocké combiné à `category` (ex.
    "documents/<nom_stocke>") forme le chemin logique à conserver dans la
    colonne du modèle appelant, exactement comme l'ancien nom de fichier sur
    disque."""
    if file is None or not file.filename:
        raise ValueError("Aucun fichier fourni")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed_ext:
        raise ValueError(f"Extension non autorisée : {ext}")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Fichier trop volumineux")
    if not _matches_magic_bytes(data, ext):
        raise ValueError("Le contenu du fichier ne correspond pas à son extension")
    stored_name = f"{uuid.uuid4().hex}{ext}"
    logical_path = f"{category}/{stored_name}"
    content_type = mimetypes.guess_type(stored_name)[0] or "application/octet-stream"
    db.add(models.StoredFile(path=logical_path, content_type=content_type, data=data))
    return stored_name, (file.filename or stored_name)


def store_bytes(db: Session, category: str, data: bytes, content_type: str, ext: str = ".pdf") -> str:
    """Enregistre des octets déjà en mémoire (ex. un PDF généré côté serveur,
    pas un upload utilisateur) en base de données. Retourne le nom stocké —
    combiné à `category` (ex. "documents/<nom_stocke>"), il forme le chemin
    logique à conserver dans la colonne du modèle appelant."""
    stored_name = f"{uuid.uuid4().hex}{ext}"
    logical_path = f"{category}/{stored_name}"
    db.add(models.StoredFile(path=logical_path, content_type=content_type, data=data))
    return stored_name


def get_stored_file(db: Session, logical_path: str | None) -> "models.StoredFile | None":
    """Retourne l'enregistrement StoredFile référencé par `logical_path`
    (ex. "documents/<uuid>.pdf"), ou None si absent ou introuvable."""
    if not logical_path:
        return None
    return db.query(models.StoredFile).filter(models.StoredFile.path == logical_path).first()


def delete_stored_file(db: Session, logical_path: str | None) -> None:
    """Supprime le fichier référencé par `logical_path`, sans effet si absent
    ou introuvable."""
    stored = get_stored_file(db, logical_path)
    if stored:
        db.delete(stored)
