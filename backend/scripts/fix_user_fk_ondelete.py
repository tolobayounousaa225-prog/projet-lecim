"""Migration ponctuelle : corrige les contraintes de clé étrangère vers users(id)
déjà créées sur Postgres pour qu'elles suivent le comportement ON DELETE désormais
défini dans les modèles (SET NULL pour préserver l'historique, CASCADE pour les
données qui n'ont pas de sens sans leur propriétaire)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2

from app.config import settings

# (table, colonne, comportement)
TARGETS = [
    ("reunions", "created_by_id", "SET NULL"),
    ("documents", "uploaded_by_id", "SET NULL"),
    ("photos", "uploaded_by_id", "SET NULL"),
    ("resultats_examens", "recorded_by_id", "SET NULL"),
    ("adhesions", "recorded_by_id", "SET NULL"),
    ("cotisations", "recorded_by_id", "SET NULL"),
    ("recettes", "recorded_by_id", "SET NULL"),
    ("depenses", "recorded_by_id", "SET NULL"),
    ("cartes_membres", "validated_by_id", "SET NULL"),
    ("partenaires", "created_by_id", "SET NULL"),
    ("projets", "created_by_id", "SET NULL"),
    ("patrimoine", "created_by_id", "SET NULL"),
    ("demandes_assistance", "recorded_by_id", "SET NULL"),
    ("publications_publiques", "uploaded_by_id", "SET NULL"),
    ("historique_presidents", "uploaded_by_id", "SET NULL"),
    ("gouvernance_membres", "uploaded_by_id", "SET NULL"),
    ("site_content", "updated_by_id", "SET NULL"),
    ("audit_logs", "user_id", "SET NULL"),
    ("sondages", "created_by_id", "SET NULL"),
    ("delegations", "created_by_id", "SET NULL"),
    ("notifications", "user_id", "CASCADE"),
    ("cartes_membres", "user_id", "CASCADE"),
    ("sondage_votes", "user_id", "CASCADE"),
]


def main() -> None:
    conn = psycopg2.connect(settings.database_url.replace("postgresql+psycopg2", "postgresql"))
    conn.autocommit = True
    cur = conn.cursor()

    for table, column, behavior in TARGETS:
        cur.execute(
            """
            SELECT tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_name = %s
              AND kcu.column_name = %s
              AND tc.constraint_type = 'FOREIGN KEY'
            """,
            (table, column),
        )
        row = cur.fetchone()
        if not row:
            print(f"SKIP {table}.{column} — aucune contrainte FK trouvée")
            continue
        constraint_name = row[0]
        cur.execute(f'ALTER TABLE {table} DROP CONSTRAINT "{constraint_name}"')
        cur.execute(
            f'ALTER TABLE {table} ADD CONSTRAINT "{constraint_name}" '
            f"FOREIGN KEY ({column}) REFERENCES users(id) ON DELETE {behavior}"
        )
        print(f"OK    {table}.{column} -> ON DELETE {behavior}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
