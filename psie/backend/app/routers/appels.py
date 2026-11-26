import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import finance, models
from ..database import get_db
from ..web import clean, parse_date, render
from .cotisations import require_finance_read, require_finance_write

router = APIRouter()


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def _parse_amount(value: str | None) -> int | None:
    value = (value or "").strip().replace(" ", "")
    if not value:
        return None
    if not value.isdigit():
        raise HTTPException(status_code=400, detail=f"Montant invalide : {value}")
    return int(value)


@router.get("/appels")
def appels_list(request: Request, user: models.User = Depends(require_finance_read), db: Session = Depends(get_db)):
    appels = db.query(models.AppelExceptionnel).order_by(models.AppelExceptionnel.id.desc()).all()
    membres = [f for f in db.query(models.Faitiere).order_by(models.Faitiere.sigle) if f.is_membre_actif]
    return render(request, "appels_list.html", user, appels=appels, membres=membres, fcfa=finance.fcfa)


@router.post("/appels")
async def appel_create(request: Request, user: models.User = Depends(require_finance_write),
                       db: Session = Depends(get_db)):
    """Formulaire : intitulé, motif, référence de la décision, date limite, montant commun et,
    pour chaque faîtière, une case « inclure » et un montant propre facultatif (qui l'emporte
    sur le montant commun)."""
    form = await request.form()
    commun = _parse_amount(form.get("montant_commun"))
    lignes = []
    for f in db.query(models.Faitiere).order_by(models.Faitiere.sigle):
        if not form.get(f"inclure_{f.id}"):
            continue
        if not f.is_membre_actif:
            raise HTTPException(status_code=400, detail=f"{f.sigle} n'est pas un membre actif")
        montant = _parse_amount(form.get(f"montant_{f.id}")) or commun
        if not montant:
            raise HTTPException(status_code=400, detail=f"Aucun montant pour {f.sigle}")
        lignes.append((f, montant))
    appel = finance.create_appel(
        db, user, str(form.get("intitule", "")), clean(form.get("motif")), clean(form.get("reference_decision")),
        parse_date(form.get("date_limite")), lignes,
    )
    db.commit()
    return _redirect(f"/appels/{appel.id}")


@router.get("/appels/{appel_id}")
def appel_detail(appel_id: int, request: Request, user: models.User = Depends(require_finance_read),
                 db: Session = Depends(get_db)):
    appel = db.get(models.AppelExceptionnel, appel_id)
    if not appel:
        raise HTTPException(status_code=404, detail="Appel introuvable")
    return render(request, "appel_detail.html", user, appel=appel, fcfa=finance.fcfa)


# ---------- Actions sur une échéance (exonération, report, correction) ----------

def _echeance(db: Session, echeance_id: int) -> models.Echeance:
    e = db.get(models.Echeance, echeance_id)
    if not e:
        raise HTTPException(status_code=404, detail="Échéance introuvable")
    return e


@router.post("/echeances/{echeance_id}/exonerer")
def echeance_exonerer(echeance_id: int, motif: str = Form(""), user: models.User = Depends(require_finance_write),
                      db: Session = Depends(get_db)):
    e = _echeance(db, echeance_id)
    finance.exonerer_echeance(db, user, e, motif)
    db.commit()
    return _redirect(f"/echeances/{e.id}")


@router.post("/echeances/{echeance_id}/retablir")
def echeance_retablir(echeance_id: int, user: models.User = Depends(require_finance_write),
                      db: Session = Depends(get_db)):
    e = _echeance(db, echeance_id)
    finance.retablir_echeance(db, user, e)
    db.commit()
    return _redirect(f"/echeances/{e.id}")


@router.post("/echeances/{echeance_id}/reporter")
def echeance_reporter(echeance_id: int, nouvelle_date: str = Form(...), motif: str = Form(""),
                      user: models.User = Depends(require_finance_write), db: Session = Depends(get_db)):
    e = _echeance(db, echeance_id)
    when = parse_date(nouvelle_date)
    if not when:
        raise HTTPException(status_code=400, detail="Nouvelle date obligatoire")
    finance.reporter_echeance(db, user, e, when, motif)
    db.commit()
    return _redirect(f"/echeances/{e.id}")


@router.post("/echeances/{echeance_id}/montant")
def echeance_montant(echeance_id: int, montant: int = Form(...), motif: str = Form(""),
                     user: models.User = Depends(require_finance_write), db: Session = Depends(get_db)):
    e = _echeance(db, echeance_id)
    finance.corriger_montant(db, user, e, montant, motif)
    db.commit()
    return _redirect(f"/echeances/{e.id}")
