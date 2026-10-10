"""Copie chiffrée des sauvegardes nocturnes vers un dépôt Git privé distinct,
pour survivre à la perte du VPS lui-même (panne disque, rançongiciel,
compromission) — une sauvegarde qui reste sur la même machine que ce qu'elle
protège n'est qu'une demi-protection. Le contenu est chiffré (Fernet) avant de
quitter le serveur : le dépôt distant ne voit jamais les données en clair,
même s'il était un jour exposé par erreur."""

import datetime
import logging
import subprocess
from pathlib import Path

from cryptography.fernet import Fernet

from .config import settings

logger = logging.getLogger("lecim.backup")

REPO_DIR = Path(__file__).resolve().parent.parent / "offsite_backup_repo"
RETENTION_COUNT = 30


def is_configured() -> bool:
    return bool(settings.backup_encryption_key and settings.backup_offsite_repo_ssh_url)


def _run_git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _ensure_repo_cloned() -> None:
    if (REPO_DIR / ".git").exists():
        return
    REPO_DIR.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", settings.backup_offsite_repo_ssh_url, str(REPO_DIR)],
        check=True, capture_output=True, text=True,
    )


def sync_latest_backup(backup_path: Path) -> bool:
    """Chiffre la sauvegarde donnée et la pousse vers le dépôt distant.
    Retourne False sans lever d'exception si la fonctionnalité n'est pas
    configurée ou si la synchronisation échoue (une sauvegarde locale réussie
    ne doit jamais être considérée en échec à cause d'un problème réseau/Git
    distinct) — l'échec est seulement journalisé."""
    if not is_configured():
        return False
    try:
        _ensure_repo_cloned()
        _run_git("pull", "--ff-only", cwd=REPO_DIR)

        fernet = Fernet(settings.backup_encryption_key.encode())
        encrypted = fernet.encrypt(backup_path.read_bytes())
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = REPO_DIR / f"lecim-{timestamp}.json.enc"
        dest.write_bytes(encrypted)

        existing = sorted(REPO_DIR.glob("lecim-*.json.enc"), key=lambda p: p.name, reverse=True)
        for old in existing[RETENTION_COUNT:]:
            old.unlink(missing_ok=True)

        _run_git("add", "-A", cwd=REPO_DIR)
        result = subprocess.run(
            ["git", "commit", "-m", f"Sauvegarde chiffrée {timestamp}"],
            cwd=REPO_DIR, capture_output=True, text=True,
        )
        if result.returncode != 0 and "nothing to commit" not in result.stdout:
            raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
        _run_git("push", cwd=REPO_DIR)
        return True
    except Exception:
        logger.exception("Échec de la synchronisation hors-site de la sauvegarde")
        return False


def decrypt_backup(encrypted_path: Path, destination: Path) -> None:
    """Déchiffre une sauvegarde hors-site récupérée depuis le dépôt distant —
    utilisé uniquement en cas de sinistre, en complément de `backup.restore_backup`."""
    fernet = Fernet(settings.backup_encryption_key.encode())
    destination.write_bytes(fernet.decrypt(encrypted_path.read_bytes()))
