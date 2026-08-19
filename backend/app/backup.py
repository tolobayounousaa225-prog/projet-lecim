"""Sauvegarde de la base de données LECIM (SQLite en développement, export JSON de
toutes les tables en production). Déclenchée automatiquement chaque nuit et
manuellement depuis l'espace admin.

Le format JSON (plutôt qu'un dump via le binaire `pg_dump`) est utilisé en
production car `pg_dump` n'est pas installé dans l'environnement d'exécution
Railway — son absence faisait échouer silencieusement toutes les sauvegardes.
Cette approche ne dépend d'aucun outil externe : uniquement de SQLAlchemy, déjà
utilisé pour se connecter à la base."""

import datetime
import decimal
import json
import shutil
from pathlib import Path

from .config import settings
from .database import Base, engine

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


def _json_default(value):
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _dump_postgres_to_json(destination: Path) -> None:
    # S'assure que tous les modèles sont enregistrés sur Base.metadata avant de
    # lister les tables (déjà garanti en pratique par l'import des routeurs admin
    # au démarrage de l'application, mais explicite ici pour rester autonome).
    from . import models  # noqa: F401

    data: dict[str, list[dict]] = {}
    with engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            rows = conn.execute(table.select()).mappings().all()
            data[table.name] = [dict(row) for row in rows]

    # Les mots de passe temporaires en clair (conservés en base comme filet de
    # secours, voir PasswordResetRequest) n'ont pas leur place dans une sauvegarde
    # téléchargeable — une fuite d'un seul fichier de sauvegarde ne doit jamais
    # exposer des identifiants valides.
    for row in data.get("password_reset_requests", []):
        if "temp_password" in row:
            row["temp_password"] = "[EXPURGÉ — voir /admin/reinitialisations]"

    with destination.open("w", encoding="utf-8") as f:
        json.dump(data, f, default=_json_default, ensure_ascii=False)


def create_backup() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    if _is_sqlite():
        source = _sqlite_path()
        destination = BACKUP_DIR / f"lecim-{timestamp}.db"
        shutil.copy2(source, destination)
    else:
        destination = BACKUP_DIR / f"lecim-{timestamp}.json"
        _dump_postgres_to_json(destination)

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
