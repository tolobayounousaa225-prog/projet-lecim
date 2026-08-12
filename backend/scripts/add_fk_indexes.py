"""Ajoute un index sur chaque colonne de clé étrangère qui n'en a pas encore.

Postgres n'indexe pas automatiquement les colonnes de clé étrangère (contrairement
aux clés primaires) — sans index, chaque jointure ou filtre sur ces colonnes force
un scan complet de la table. Avec la multiplication des tables cette session
(effectifs, cartes_scolaires, messages_etablissements, annonces_delegations...),
ce script comble ce manque une bonne fois pour toutes via une introspection du
schéma réel, plutôt que de lister les colonnes à la main."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2

from app.config import settings

url = settings.database_url.replace("postgresql+psycopg2", "postgresql")
conn = psycopg2.connect(url)
conn.autocommit = True
cur = conn.cursor()

cur.execute(
    """
    SELECT tc.table_name, kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
    ORDER BY tc.table_name, kcu.column_name
    """
)
fk_columns = cur.fetchall()
print(f"{len(fk_columns)} colonnes de clé étrangère trouvées.")

created = 0
for table_name, column_name in fk_columns:
    index_name = f"ix_{table_name}_{column_name}"
    cur.execute(
        """
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'public' AND tablename = %s
          AND indexdef LIKE %s
        """,
        (table_name, f"%({column_name})%"),
    )
    if cur.fetchone():
        continue
    cur.execute(f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table_name}" ("{column_name}")')
    print(f"  + index créé : {index_name}")
    created += 1

print(f"Terminé — {created} nouveaux index créés, {len(fk_columns) - created} déjà couverts.")
cur.close()
conn.close()
