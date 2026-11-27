"""Mandats et composition des organes (Statuts de la PSIE)."""

import datetime

from sqlalchemy.orm import Session

from . import models


def mandat_actif(m: models.Mandat, jour: datetime.date) -> bool:
    return (m.date_debut is None or m.date_debut <= jour) and (m.date_fin is None or m.date_fin >= jour)


def composition_organes(db: Session, jour: datetime.date | None = None) -> list[dict]:
    """Effectifs réels des organes comparés à ceux des Statuts (CA 13, DEN 13, CC 2) et des
    délégués à l'AG (2 par organisation membre active)."""
    jour = jour or datetime.date.today()
    actifs = [m for m in db.query(models.Mandat) if mandat_actif(m, jour)]
    rows = [{"organe": o, "attendu": n, "reel": sum(1 for m in actifs if m.organe == o)}
            for o, n in models.COMPOSITION_ATTENDUE.items()]
    membres = sum(1 for f in db.query(models.Faitiere) if f.is_membre_actif)
    rows.append({"organe": "AG", "attendu": 2 * membres,
                 "reel": sum(1 for m in actifs if m.organe == "AG" and m.faitiere and m.faitiere.is_membre_actif)})
    return rows
