"""Migrations idempotentes exécutées à chaque démarrage de l'application — sans
dépendance à un outil de migration externe. Chaque étape se protège elle-même par
une vérification d'état avant d'agir, donc elle n'a plus aucun effet après son
premier passage réussi."""

from sqlalchemy import inspect, text

from .database import Base, engine


def run_startup_migrations() -> None:
    inspector = inspect(engine)

    if inspector.has_table("adhesion_requests"):
        columns = {c["name"] for c in inspector.get_columns("adhesion_requests")}
        if "code_demande" not in columns:
            # Ancien schéma (fonctionnalité introduite juste avant ce circuit complet,
            # sans donnée réelle en production) — recréée avec le nouveau schéma.
            with engine.begin() as conn:
                conn.execute(text("DROP TABLE adhesion_requests CASCADE"))

    Base.metadata.create_all(bind=engine)
