"""Tableau de bord admin des statistiques de fréquentation de la vitrine —
lecture agrégée des compteurs de vues collectés par routers/stats.py."""

import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_publications_access_web

router = APIRouter(prefix="/admin", tags=["admin-statistiques"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/statistiques")
def statistiques_dashboard(
    request: Request,
    jours: int = 30,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    jours = jours if jours in (7, 30, 90) else 30
    date_debut = datetime.date.today() - datetime.timedelta(days=jours - 1)

    vues_par_jour = dict(
        db.query(models.PageView.date, func.coalesce(func.sum(models.PageView.views), 0))
        .filter(models.PageView.date >= date_debut)
        .group_by(models.PageView.date)
        .all()
    )
    serie = []
    for i in range(jours):
        d = date_debut + datetime.timedelta(days=i)
        serie.append({"date": d, "vues": vues_par_jour.get(d, 0)})
    total_vues = sum(s["vues"] for s in serie)

    top_pages = (
        db.query(models.PageView.path, func.sum(models.PageView.views).label("total"))
        .filter(models.PageView.date >= date_debut)
        .group_by(models.PageView.path)
        .order_by(func.sum(models.PageView.views).desc())
        .limit(15)
        .all()
    )

    chart_width, chart_height = 760, 200
    max_val = max([1] + [s["vues"] for s in serie])
    slot_width = chart_width / jours
    bar_width = max(2, slot_width - 2)
    bars = [
        {
            "x": i * slot_width,
            "y": chart_height - (s["vues"] / max_val) * chart_height,
            "width": bar_width,
            "height": (s["vues"] / max_val) * chart_height,
        }
        for i, s in enumerate(serie)
    ]

    return templates.TemplateResponse(
        request,
        "admin/statistiques_dashboard.html",
        {
            "admin": user,
            "active": "statistiques",
            "jours": jours,
            "date_debut": date_debut,
            "date_fin": datetime.date.today(),
            "total_vues": total_vues,
            "top_pages": top_pages,
            "bars": bars,
            "chart_width": chart_width,
            "chart_height": chart_height,
        },
    )
