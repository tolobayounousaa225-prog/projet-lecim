"""Rapprochement des dons déclarés en libre-service depuis la vitrine — le
financier confirme (en comptabilisant une recette) ou supprime (doublon, spam)."""

from pathlib import Path

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import audit, models
from ..attestations_pdf import generate_don_recu_pdf, numero_recu_don
from ..database import get_db
from ..deps import require_finance_access_web
from ..email_utils import send_email_with_attachment

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
    # Verrou de ligne : deux clics rapprochés (double-clic, connexion lente) sur le
    # même don ne doivent jamais créer deux Recette pour un seul don confirmé.
    don = db.query(models.DonDeclare).filter(models.DonDeclare.id == don_id).with_for_update().first()
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

        if don.email:
            try:
                pdf_bytes = generate_don_recu_pdf(don)
                send_email_with_attachment(
                    don.email,
                    "Reçu de votre don à la LECIM",
                    f"Bonjour {don.nom_donateur},\n\n"
                    "Nous vous remercions chaleureusement pour votre don à la LECIM. "
                    "Vous trouverez en pièce jointe votre reçu officiel.\n\n"
                    "LECIM — Ligue des Établissements Confessionnels et Madrassas de Côte d'Ivoire",
                    pdf_bytes,
                    f"{numero_recu_don(don.id)}.pdf",
                )
            except Exception:
                pass
    return RedirectResponse(url="/admin/dons", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{don_id}/recu.pdf")
def don_recu_pdf(
    don_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    don = db.get(models.DonDeclare, don_id)
    if not don or not don.is_confirme:
        return RedirectResponse(url="/admin/dons", status_code=status.HTTP_303_SEE_OTHER)
    pdf_bytes = generate_don_recu_pdf(don)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{numero_recu_don(don.id)}.pdf"'},
    )


@router.post("/{don_id}/delete")
def don_delete(
    don_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    # Verrou identique à don_confirmer : sans lui, une confirmation concurrente
    # entre la lecture et la suppression pourrait effacer un don qui vient
    # d'être confirmé et comptabilisé (le solde du don reste dans la Recette,
    # mais la trace du don lui-même — nom, e-mail, historique — serait perdue).
    don = db.query(models.DonDeclare).filter(models.DonDeclare.id == don_id).with_for_update().first()
    if don and not don.is_confirme:
        audit.log(db, user, "delete", "Don déclaré", don.id, f"A supprimé la déclaration de don de {don.nom_donateur}")
        db.delete(don)
        db.commit()
    return RedirectResponse(url="/admin/dons", status_code=status.HTTP_303_SEE_OTHER)
