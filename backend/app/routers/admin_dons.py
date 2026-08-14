"""Rapprochement des dons déclarés en libre-service depuis la vitrine — le
financier confirme (en comptabilisant une recette) ou supprime (doublon, spam)."""

from pathlib import Path

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import audit, models
from ..database import get_db
from ..deps import require_finance_access_web

router = APIRouter(prefix="/admin/dons", tags=["admin-dons"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def dons_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    items = (
        db.query(models.DonDeclare)
        .order_by(models.DonDeclare.is_confirme, models.DonDeclare.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/dons_list.html",
        {"admin": user, "items": items, "active": "dons"},
    )


@router.post("/{don_id}/confirmer")
def don_confirmer(
    don_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    don = db.get(models.DonDeclare, don_id)
    if don and not don.is_confirme:
        recette = models.Recette(
            categorie="don_legs",
            libelle=f"Don de {don.nom_donateur}",
            montant=don.montant,
            date=don.date_don,
            recorded_by_id=user.id,
        )
        db.add(recette)
        db.flush()
        don.is_confirme = True
        don.confirme_par_id = user.id
        don.recette_id = recette.id
        audit.log(
            db, user, "update", "Don déclaré", don.id,
            f"A confirmé et comptabilisé le don de {don.nom_donateur} ({don.montant} FCFA)",
        )
        db.commit()
    return RedirectResponse(url="/admin/dons", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{don_id}/delete")
def don_delete(
    don_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    don = db.get(models.DonDeclare, don_id)
    if don and not don.is_confirme:
        audit.log(db, user, "delete", "Don déclaré", don.id, f"A supprimé la déclaration de don de {don.nom_donateur}")
        db.delete(don)
        db.commit()
    return RedirectResponse(url="/admin/dons", status_code=status.HTTP_303_SEE_OTHER)
