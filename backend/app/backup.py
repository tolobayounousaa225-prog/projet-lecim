"""Sauvegarde de la base de données LECIM (SQLite en développement, PostgreSQL en
production via pg_dump). Déclenchée automatiquement chaque nuit et manuellement
depuis l'espace admin."""

import datetime
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from .config import settings

BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"
RETENTION_COUNT = 30


def _is_sqlite() -> bool:
    return settings.database_url.startswith("sqlite")


def _sqlite_path() -> Path:
    # sqlite:///./lecim_dev.db  ->  ./lecim_dev.db (relatif au dossier backend/)
    raw = settings.database_url.split("///", 1)[1]
    path = Path(raw)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
    return path


def create_backup() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    if _is_sqlite():
        source = _sqlite_path()
        destination = BACKUP_DIR / f"lecim-{timestamp}.db"
        shutil.copy2(source, destination)
    else:
        destination = BACKUP_DIR / f"lecim-{timestamp}.sql"
        parsed = urlparse(settings.database_url.replace("postgresql+psycopg2", "postgresql"))
        env_args = [
            "pg_dump",
            "--no-owner",
            "--no-privileges",
            "-h", parsed.hostname or "localhost",
            "-p", str(parsed.port or 5432),
            "-U", parsed.username or "postgres",
            "-d", (parsed.path or "/lecim").lstrip("/"),
            "-f", str(destination),
        ]
        import os

        env = os.environ.copy()
        if parsed.password:
            env["PGPASSWORD"] = parsed.password
        subprocess.run(env_args, check=True, env=env)

    _cleanup_old_backups()
    return destination


def _cleanup_old_backups(keep: int = RETENTION_COUNT) -> None:
    backups = sorted(BACKUP_DIR.glob("lecim-*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[keep:]:
        old.unlink(missing_ok=True)


def list_backups() -> list[dict]:
    if not BACKUP_DIR.exists():
        return []
    backups = sorted(BACKUP_DIR.glob("lecim-*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {
            "filename": p.name,
            "size_kb": round(p.stat().st_size / 1024, 1),
            "created_at": datetime.datetime.fromtimestamp(p.stat().st_mtime),
        }
        for p in backups
    ]
