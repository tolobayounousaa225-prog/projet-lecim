import datetime
import io

import hmac
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from .. import finance, models, pdfs
from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..web import clean, parse_date, render

router = APIRouter()


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def require_finance_read(user: models.User = Depends(get_current_user)) -> models.User:
    if not user.can_view_finances:
        raise HTTPException(status_code=403, detail="Accès réservé aux organes chargés des finances et du contrôle")
    return user


def require_finance_write(user: models.User = Depends(get_current_user)) -> models.User:
    if not user.can_write_finances:
        raise HTTPException(status_code=403, detail="Action réservée au secrétaire chargé des finances")
    return user


def _can_see_echeance(user: models.User, e: models.Echeance) -> bool:
    """Lecture financière pour les organes autorisés ; un représentant ne voit que sa faîtière."""
    return user.can_view_finances or (not user.is_internal and user.can_view_faitiere(e.faitiere_id))


def _get_echeance(user: models.User, echeance_id: int, db: Session) -> models.Echeance:
    e = db.get(models.Echeance, echeance_id)
    if not e or not _can_see_echeance(user, e):
        raise HTTPException(status_code=404, detail="Échéance introuvable")
    return e


def _get_paiement(user: models.User, paiement_id: int, db: Session) -> models.Paiement:
    p = db.get(models.Paiement, paiement_id)
    if not p or not _can_see_echeance(user, p.echeance):
        raise HTTPException(status_code=404, detail="Paiement introuvable")
    return p


# ---------- Vue d'ensemble ----------

@router.get("/cotisations")
def cotisations_page(request: Request, annee: int | None = None, user: models.User = Depends(require_finance_read),
                     db: Session = Depends(get_db)):
    annee = annee or datetime.date.today().year
    data = finance.situation(db, annee)
    bareme = db.query(models.BaremeCotisation).filter_by(annee=annee).first()
    manquantes = sum(
        1 for f in db.query(models.Faitiere).all()
        if f.is_membre_actif and not any(e.faitiere_id == f.id for e in data["rows"])
    )
    faitieres = db.query(models.Faitiere).order_by(models.Faitiere.sigle).all()
    return render(request, "cotisations.html", user, data=data, bareme=bareme, annee=annee,
                  manquantes=manquantes, faitieres=faitieres, fcfa=finance.fcfa)


@router.get("/cotisations/export.csv")
def cotisations_csv(annee: int | None = None, user: models.User = Depends(require_finance_read),
                    db: Session = Depends(get_db)):
    annee = annee or datetime.date.today().year
    content = finance.situation_csv(finance.situation(db, annee))
    return Response(
        "﻿" + content, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="cotisations-{annee}.csv"'},
    )


@router.post("/cotisations/bareme")
def bareme_save(annee: int = Form(...), montant: int = Form(...), date_limite: str = Form(""),
                reference_decision: str = Form(""), user: models.User = Depends(require_finance_write),
                db: Session = Depends(get_db)):
    finance.set_bareme(db, user, annee, montant, parse_date(date_limite), clean(reference_decision))
    db.commit()
    return _redirect(f"/cotisations?annee={annee}")


@router.post("/cotisations/ouvrir")
def annee_open(annee: int = Form(...), user: models.User = Depends(require_finance_write),
               db: Session = Depends(get_db)):
    finance.generate_annual_echeances(db, annee, user)
    db.commit()
    return _redirect(f"/cotisations?annee={annee}")


@router.post("/echeances/adhesion")
def adhesion_create(faitiere_id: int = Form(...), montant: int = Form(...), date_limite: str = Form(""),
                    reference_decision: str = Form(""), user: models.User = Depends(require_finance_write),
                    db: Session = Depends(get_db)):
    faitiere = db.get(models.Faitiere, faitiere_id)
    if not faitiere:
        raise HTTPException(status_code=400, detail="Faîtière inconnue")
    e = finance.create_adhesion_echeance(db, user, faitiere, montant, parse_date(date_limite), clean(reference_decision))
    db.commit()
    return _redirect(f"/echeances/{e.id}")


# ---------- Échéance et paiements ----------

@router.get("/echeances/{echeance_id}")
def echeance_detail(echeance_id: int, request: Request, user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    e = _get_echeance(user, echeance_id, db)
    return render(request, "echeance_detail.html", user, e=e, fcfa=finance.fcfa,
                  modes=models.MODES_PAIEMENT, today=datetime.date.today())


@router.post("/echeances/{echeance_id}/paiements")
def paiement_create(echeance_id: int, montant: int = Form(...), date_paiement: str = Form(...),
                    mode: str = Form(...), reference: str = Form(""),
                    user: models.User = Depends(require_finance_write), db: Session = Depends(get_db)):
    e = db.get(models.Echeance, echeance_id)
    if not e:
        raise HTTPException(status_code=404, detail="Échéance introuvable")
    when = parse_date(date_paiement)
    if not when:
        raise HTTPException(status_code=400, detail="Date de paiement obligatoire")
    finance.record_paiement(db, user, e, montant, when, mode, clean(reference))
    db.commit()
    return _redirect(f"/echeances/{e.id}")


@router.post("/paiements/{paiement_id}/annuler")
def paiement_cancel(paiement_id: int, motif: str = Form(""), user: models.User = Depends(require_finance_write),
                    db: Session = Depends(get_db)):
    p = db.get(models.Paiement, paiement_id)
    if not p:
        raise HTTPException(status_code=404, detail="Paiement introuvable")
    finance.cancel_paiement(db, user, p, motif)
    db.commit()
    return _redirect(f"/echeances/{p.echeance_id}")


def _pdf_response(content: bytes, filename: str) -> Response:
    return Response(content, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


@router.get("/paiements/{paiement_id}/recu.pdf")
def recu_pdf(paiement_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _get_paiement(user, paiement_id, db)
    return _pdf_response(pdfs.receipt_pdf(p), f"{p.recu_numero}.pdf")


@router.get("/faitieres/{faitiere_id}/attestation.pdf")
def attestation_pdf(faitiere_id: int, annee: int | None = None, user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    # Organes de finances/contrôle : toutes les faîtières ; représentant : la sienne seulement
    if not (user.can_view_finances or (not user.is_internal and user.can_view_faitiere(faitiere_id))):
        raise HTTPException(status_code=404, detail="Faîtière introuvable")
    faitiere = db.get(models.Faitiere, faitiere_id)
    if not faitiere:
        raise HTTPException(status_code=404, detail="Faîtière introuvable")
    annee = annee or datetime.date.today().year
    e = db.query(models.Echeance).filter_by(faitiere_id=faitiere_id, type="annuelle", annee=annee).first()
    if not e or e.solde > 0:
        raise HTTPException(status_code=409, detail=f"{faitiere.sigle} n'est pas à jour de sa cotisation {annee}")
    sig = finance.attestation_signature(faitiere_id, annee)
    url = f"{settings.public_base_url.rstrip('/')}/verifier/attestation/{faitiere_id}/{annee}/{sig}"
    return _pdf_response(pdfs.attestation_pdf(faitiere, annee, e, url), f"attestation-{faitiere.sigle}-{annee}.pdf")


# ---------- Vérification publique (QR codes) ----------

@router.get("/verifier/attestation/{faitiere_id}/{annee}/{sig}")
def verify_attestation(faitiere_id: int, annee: int, sig: str, request: Request, db: Session = Depends(get_db)):
    if not hmac.compare_digest(sig, finance.attestation_signature(faitiere_id, annee)):
        raise HTTPException(status_code=404, detail="Attestation non reconnue")
    faitiere = db.get(models.Faitiere, faitiere_id)
    if not faitiere:
        raise HTTPException(status_code=404, detail="Attestation non reconnue")
    return render(request, "verifier.html", None, kind="attestation", faitiere=faitiere, annee=annee,
                  a_jour=finance.faitiere_a_jour(db, faitiere_id, annee))


@router.get("/verifier/{token}")
def verify_receipt(token: str, request: Request, db: Session = Depends(get_db)):
    p = db.query(models.Paiement).filter_by(verify_token=token).first()
    if not p:
        raise HTTPException(status_code=404, detail="Reçu non reconnu")
    # Page publique : seulement le strict nécessaire (pas de coordonnées, pas de solde)
    return render(request, "verifier.html", None, kind="recu", p=p, fcfa=finance.fcfa)
