"""Crée une base de test avec quelques comptes et données (utilisée par les tests de navigateur)."""
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app import models  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.security import hash_password  # noqa: E402

PASSWORD = "Motdepasse-Test-1"


def main() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    year = datetime.date.today().year
    federations = {}
    for n in ("LECIM", "IQRA", "OEECI", "CHERIFLA", "AL HIKMA", "HINNEH", "NOUR"):
        f = models.Faitiere(sigle=n, nom=f"Organisation {n}", categorie="fondateur", statut="actif", date_adhesion=datetime.date(2021, 9, 3))
        db.add(f)
        db.flush()
        federations[n] = f
        e = models.Ecole(faitiere_id=f.id, nom=f"École {n}", niveau="primaire", localite="Abidjan")
        db.add(e)
        db.flush()
        db.add(models.RecensementEcole(ecole_id=e.id, annee=year, eleves=250, admin_francophone=2, admin_arabisant=1, ens_francophone=8, ens_arabisant=5))
        db.add(models.ResultatExamen(ecole_id=e.id, annee=year, examen="cepe", inscrits=40, admis=30))
    for email, role in (("den@psie.ci", "den"), ("admin@psie.ci", "admin"), ("fin@psie.ci", "finances"), ("com@psie.ci", "communication")):
        db.add(models.User(email=email, full_name=f"Test {role}", role=role, hashed_password=hash_password(PASSWORD)))
    db.add(models.User(email="rep@psie.ci", full_name="Représentant LECIM", role="faitiere", faitiere_id=federations["LECIM"].id,
                       hashed_password=hash_password(PASSWORD)))
    db.commit()


if __name__ == "__main__":
    main()
