import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from .. import gouvernance, models, pdfs
from ..audit import log_action
from ..database import get_db
from ..deps import require_internal, require_member_manager
from ..web import parse_date, render

router = APIRouter()


@router.get("/sanctions")
def sanctions_list(request: Request, user: models.User = Depends(require_internal), db: Session = Depends(get_db)):
    items = db.query(models.Sanction).order_by(models.Sanction.id.desc()).all()
    faitieres = [f for f in db.query(models.Faitiere).order_by(models.Faitiere.sigle) if f.categorie != "honneur"]
    return render(request, "sanctions_list.html", user, items=items, faitieres=faitieres, types=models.SANCTION_TYPES)


@router.post("/sanctions")
def sanction_create(faitiere_id: int = Form(...), type: str = Form(...), motif: str = Form(""),
                    reference: str = Form(""), date_decision: str = Form(""),
                    user: models.User = Depends(require_member_manager), db: Session = Depends(get_db)):
    faitiere = db.get(models.Faitiere, faitiere_id)
    if not faitiere:
        raise HTTPException(status_code=400, detail="Organisation inconnue")
    s = gouvernance.pronounce_sanction(db, user, faitiere, type, motif, reference,
                                       parse_date(date_decision) or datetime.date.today())
    db.commit()
    return RedirectResponse(f"/sanctions#s{s.id}", status_code=303)


@router.post("/sanctions/{sanction_id}/notifier")
def sanction_notify(sanction_id: int, user: models.User = Depends(require_member_manager), db: Session = Depends(get_db)):
    s = db.get(models.Sanction, sanction_id)
    if not s:
        raise HTTPException(status_code=404, detail="Sanction introuvable")
    s.notifiee_le = datetime.date.today()
    log_action(db, user, "notification", "sanction", s.id, s.faitiere.sigle)
    db.commit()
    return RedirectResponse("/sanctions", status_code=303)


@router.post("/sanctions/{sanction_id}/lever")
def sanction_lift(sanction_id: int, motif: str = Form(""), user: models.User = Depends(require_member_manager),
                  db: Session = Depends(get_db)):
    s = db.get(models.Sanction, sanction_id)
    if not s:
        raise HTTPException(status_code=404, detail="Sanction introuvable")
    gouvernance.lift_suspension(db, user, s, motif)
    db.commit()
    return RedirectResponse("/sanctions", status_code=303)


@router.get("/sanctions/{sanction_id}/notification.pdf")
def sanction_pdf(sanction_id: int, user: models.User = Depends(require_internal), db: Session = Depends(get_db)):
    s = db.get(models.Sanction, sanction_id)
    if not s:
        raise HTTPException(status_code=404, detail="Sanction introuvable")
    return Response(pdfs.sanction_pdf(s), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="sanction-{s.faitiere.sigle}-{s.id}.pdf"'})
