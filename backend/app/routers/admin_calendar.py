import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_login_web
from ..reports import current_annee_scolaire, etablissements_en_retard

router = APIRouter(prefix="/admin", tags=["admin-calendar"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def _cotisation_echeance(annee_scolaire: str) -> datetime.date:
    """Date limite nominale de paiement : fin du 1er trimestre de la rentrée (30 novembre)."""
    start_year = int(annee_scolaire.split("-")[0])
    return datetime.date(start_year, 11, 30)


@router.get("/calendrier")
def calendrier(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_web),
):
    events = []

    if user.can_manage_reunions:
        for r in db.query(models.Reunion).filter(models.Reunion.delegation_id.is_(None)).all():
            events.append(
                {
                    "date": r.date,
                    "title": r.title,
                    "type": "reunion",
                    "type_label": "Réunion",
                    "detail": r.lieu,
                    "link": f"/admin/reunions/{r.id}",
                }
            )

    for a in db.query(models.Activity).all():
        events.append(
            {
                "date": a.event_date,
                "title": a.title,
                "type": "activite",
                "type_label": "Activité",
                "detail": None,
                "link": None,
            }
        )

    if user.can_manage_finances:
        annee = current_annee_scolaire()
        echeance = _cotisation_echeance(annee)
        for r in etablissements_en_retard(db, annee):
            events.append(
                {
                    "date": echeance,
                    "title": f"Cotisation {annee} — {r['etablissement'].nom}",
                    "type": "cotisation",
                    "type_label": "Échéance cotisation",
                    "detail": f"Reste dû : {r['reste']:,} FCFA".replace(",", " "),
                    "link": "/admin/finances/retards",
                }
            )

    events.sort(key=lambda e: e["date"])

    today = datetime.date.today()
    a_venir = [e for e in events if e["date"] >= today]
    passes = [e for e in events if e["date"] < today]
    passes.reverse()

    return templates.TemplateResponse(
        request,
        "admin/calendrier.html",
        {"admin": user, "a_venir": a_venir, "passes": passes, "active": "calendrier"},
    )
