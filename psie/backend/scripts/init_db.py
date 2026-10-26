"""Crée les tables, le compte administrateur initial et les 6 membres fondateurs.

Usage:
    python -m scripts.init_db

Idempotent : peut être relancé sans créer de doublons.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app import models
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.security import hash_password

# Membres fondateurs (Règlement Intérieur, art. 21). Les noms complets sont à renseigner
# depuis l'espace d'administration ; en attendant, le sigle sert de nom.
FONDATEURS = [
    ("OEECI", "OEECI"),
    ("LECIM", "LECIM"),
    ("IQRA", "IQRA"),
    ("CHERIFLA", "CHERIFLA"),
    ("AL HIKMA", "AL HIKMA"),
    ("HINNEH", "HINNEH"),
]


def run() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _ensure_admin(db)
        _ensure_fondateurs(db)
        db.commit()
    finally:
        db.close()


def _ensure_admin(db) -> None:
    email = settings.admin_bootstrap_email.strip().lower()
    if db.query(models.User).filter(models.User.email == email).first():
        print(f"Admin déjà présent : {email}")
        return
    db.add(
        models.User(
            email=email,
            hashed_password=hash_password(settings.admin_bootstrap_password),
            full_name=settings.admin_bootstrap_name,
            role="admin",
        )
    )
    print(f"Compte administrateur créé : {email}")


def _ensure_fondateurs(db) -> None:
    for sigle, nom in FONDATEURS:
        if db.query(models.Faitiere).filter(models.Faitiere.sigle == sigle).first():
            continue
        db.add(models.Faitiere(sigle=sigle, nom=nom, categorie="fondateur", statut="actif"))
        print(f"Membre fondateur créé : {sigle}")


if __name__ == "__main__":
    run()
