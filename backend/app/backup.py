"""Sauvegarde de la base de données LECIM (SQLite en développement, export JSON de
toutes les tables en production). Déclenchée automatiquement chaque nuit et
manuellement depuis l'espace admin.

Le format JSON (plutôt qu'un dump via le binaire `pg_dump`) est utilisé en
production car `pg_dump` n'est pas installé dans l'environnement d'exécution
Railway — son absence faisait échouer silencieusement toutes les sauvegardes.
Cette approche ne dépend d'aucun outil externe : uniquement de SQLAlchemy, déjà
utilisé pour se connecter à la base."""

import base64
import datetime
import decimal
import json
import shutil
from pathlib import Path

from .config import settings
from .database import Base, engine

# Marqueur distinguant une valeur binaire encodée en base64 (fichiers uploadés
# stockés dans StoredFile.data) d'une chaîne de texte normale, pour pouvoir la
# décoder sans ambiguïté à la restauration.
_BYTES_MARKER = "__lecim_bytes_b64__"

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
        # Encodage réversible (base64), pas un décodage UTF-8 avec remplacement
        # des octets invalides : les fichiers uploadés (StoredFile.data — PDF,
        # photos, logos) sont du binaire arbitraire, pas du texte. Un décodage
        # UTF-8 "errors=replace" les aurait irrémédiablement corrompus.
        return {_BYTES_MARKER: base64.b64encode(value).decode("ascii")}
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


def _coerce_row_for_restore(table, row: dict) -> dict:
    """Inverse les conversions appliquées par `_json_default` à la sauvegarde :
    décode le binaire (base64 -> bytes) et reparse les dates/horodatages
    (chaîne ISO -> date/datetime), en se basant sur le type déclaré de chaque
    colonne — pas sur la forme de la valeur, pour ne jamais confondre une
    simple chaîne qui ressemble à une date (ex. `annee_scolaire`) avec une
    vraie colonne Date/DateTime."""
    coerced = dict(row)
    for column in table.columns:
        value = coerced.get(column.name)
        if isinstance(value, dict) and _BYTES_MARKER in value:
            coerced[column.name] = base64.b64decode(value[_BYTES_MARKER])
        elif isinstance(value, str) and value:
            python_type = getattr(column.type, "python_type", None)
            if python_type is datetime.datetime:
                coerced[column.name] = datetime.datetime.fromisoformat(value)
            elif python_type is datetime.date:
                coerced[column.name] = datetime.date.fromisoformat(value)
    return coerced


def restore_backup(source: Path) -> dict[str, int]:
    """Restaure une sauvegarde JSON (format produit par `_dump_postgres_to_json`)
    dans la base de données actuellement configurée — remplace entièrement le
    contenu de chaque table présente dans la sauvegarde. Usage exclusivement en
    cas de sinistre (perte/corruption de la base) : à lancer manuellement
    (SSH + console Python), jamais exposé comme bouton web — une restauration
    écrase irréversiblement les données actuelles, un mauvais clic ne doit pas
    pouvoir la déclencher. Retourne le nombre de lignes restaurées par table."""
    from . import models  # noqa: F401 — enregistre tous les modèles sur Base.metadata

    with source.open("r", encoding="utf-8") as f:
        data: dict[str, list[dict]] = json.load(f)

    restored: dict[str, int] = {}
    # Colonnes de clé étrangère nullable, par table : certaines tables se
    # référencent mutuellement (ex. users <-> delegations <-> etablissements),
    # ce qui rend tout ordre d'insertion unique impossible à garantir sans
    # violer une contrainte. On insère donc en deux passes : d'abord toutes
    # les lignes avec ces colonnes à NULL (aucune ligne n'en référence alors
    # une autre), puis une passe de UPDATE qui rétablit les vraies valeurs une
    # fois que toutes les lignes existent.
    nullable_fk_columns = {
        table.name: [c for c in table.columns if c.foreign_keys and c.nullable]
        for table in Base.metadata.sorted_tables
    }

    with engine.begin() as conn:
        # Ordre inverse (enfants avant parents) pour la suppression, afin de
        # respecter les contraintes de clé étrangère ; ordre normal (parents
        # avant enfants) pour la réinsertion — approximatif en cas de cycle,
        # mais sans conséquence puisque ces colonnes sont nullées en première passe.
        for table in reversed(Base.metadata.sorted_tables):
            if table.name in data:
                conn.execute(table.delete())

        for table in Base.metadata.sorted_tables:
            rows = data.get(table.name)
            if not rows:
                restored[table.name] = 0
                continue
            fk_cols = [c.name for c in nullable_fk_columns[table.name]]
            insert_rows = []
            for row in rows:
                coerced = _coerce_row_for_restore(table, row)
                for col_name in fk_cols:
                    coerced[col_name] = None
                insert_rows.append(coerced)
            conn.execute(table.insert(), insert_rows)
            restored[table.name] = len(rows)

        pk_cols_by_table = {table.name: list(table.primary_key.columns) for table in Base.metadata.sorted_tables}
        for table in Base.metadata.sorted_tables:
            fk_cols = nullable_fk_columns[table.name]
            rows = data.get(table.name)
            pk_cols = pk_cols_by_table[table.name]
            if not rows or not fk_cols or not pk_cols:
                continue
            for row in rows:
                coerced = _coerce_row_for_restore(table, row)
                real_values = {c.name: coerced.get(c.name) for c in fk_cols}
                if all(v is None for v in real_values.values()):
                    continue
                where_clause = True
                for pk in pk_cols:
                    where_clause = (pk == row[pk.name]) if where_clause is True else (where_clause & (pk == row[pk.name]))
                conn.execute(table.update().where(where_clause).values(**real_values))

    return restored


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
