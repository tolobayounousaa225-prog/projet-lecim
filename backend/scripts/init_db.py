"""Crée les tables, le compte administrateur initial et des données de démonstration.

Usage:
    python -m scripts.init_db
"""
import datetime
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.database import Base, SessionLocal, engine
from app import models
from app.security import hash_password


def run() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _ensure_admin(db)
        _seed_demo_content(db)
        db.commit()
    finally:
        db.close()


def _ensure_admin(db) -> None:
    existing = (
        db.query(models.User)
        .filter(models.User.email == settings.admin_bootstrap_email)
        .first()
    )
    if existing:
        print(f"Admin déjà présent : {existing.email}")
        return
    admin = models.User(
        email=settings.admin_bootstrap_email,
        hashed_password=hash_password(settings.admin_bootstrap_password),
        full_name=settings.admin_bootstrap_name,
        access_level="admin",
    )
    db.add(admin)
    print(f"Compte administrateur créé : {admin.email}")


def _seed_demo_content(db) -> None:
    if db.query(models.NewsPost).count() == 0:
        db.add_all(
            [
                models.NewsPost(
                    title="Réunion du Bureau Exécutif National",
                    excerpt=(
                        "Le Bureau Exécutif National de la LECIM s'est réuni pour valider les "
                        "matrices d'action 2026, en présence des responsables régionaux."
                    ),
                    content="",
                    published_at=datetime.date(2025, 12, 28),
                    is_published=True,
                ),
                models.NewsPost(
                    title="Lancement de la plateforme de gestion scolaire",
                    excerpt=(
                        "La LECIM déploie sa nouvelle application de gestion des écoles "
                        "confessionnelles auprès des premiers établissements pilotes."
                    ),
                    content="",
                    published_at=datetime.date(2025, 12, 15),
                    is_published=True,
                ),
                models.NewsPost(
                    title="Formation des directeurs d'établissements",
                    excerpt=(
                        "Un séminaire régional a réuni les directeurs des écoles confessionnelles "
                        "et madrassas autour des bonnes pratiques pédagogiques et administratives."
                    ),
                    content="",
                    published_at=datetime.date(2025, 11, 20),
                    is_published=True,
                ),
            ]
        )
        print("Actualités de démonstration ajoutées.")

    if db.query(models.Activity).count() == 0:
        today = datetime.date.today()

        def offset(days: int) -> datetime.date:
            return today + datetime.timedelta(days=days)

        db.add_all(
            [
                models.Activity(
                    title="Rentrée scolaire des établissements membres",
                    description=(
                        "Coordination de la rentrée scolaire dans les écoles "
                        "confessionnelles et madrassas affiliées à la LECIM."
                    ),
                    event_date=offset(-90),
                ),
                models.Activity(
                    title="Séminaire de formation des directeurs",
                    description=(
                        "Formation régionale des directeurs sur la gestion administrative, "
                        "pédagogique et l'utilisation de la plateforme numérique de la LECIM."
                    ),
                    event_date=offset(-60),
                ),
                models.Activity(
                    title="Réunion du Bureau Exécutif National",
                    description=(
                        "Validation des matrices d'action annuelles en présence des membres "
                        "du Bureau Exécutif National et des responsables régionaux."
                    ),
                    event_date=offset(-21),
                ),
                models.Activity(
                    title="Assemblée générale régionale — Gôh",
                    description=(
                        "La délégation régionale du Gôh organise son assemblée générale "
                        "à Gagnoa, réunissant les établissements membres de la région."
                    ),
                    event_date=offset(-7),
                ),
                models.Activity(
                    title="Session des examens scolaires islamiques",
                    description=(
                        "Organisation, en collaboration avec le ministère de l'Éducation "
                        "nationale, des examens scolaires islamiques pour les élèves membres."
                    ),
                    event_date=offset(30),
                ),
                models.Activity(
                    title="Assemblée Générale Nationale de la LECIM",
                    description=(
                        "Grand rassemblement national des établissements confessionnels et "
                        "madrassas membres à Abidjan pour le bilan annuel et les perspectives."
                    ),
                    event_date=offset(60),
                ),
            ]
        )
        print("Activités de démonstration ajoutées.")


if __name__ == "__main__":
    run()
