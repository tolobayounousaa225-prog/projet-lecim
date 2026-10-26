"""Assemblées générales : préparation, convocation, séance, scrutins, procès-verbal."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from .. import finance, gouvernance, models, pdfs
from ..database import get_db
from ..deps import get_current_user, require_internal, require_member_manager
from ..web import parse_date, render

router = APIRouter()


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def _get(db: Session, assemblee_id: int) -> models.Assemblee:
    a = db.get(models.Assemblee, assemblee_id)
    if not a:
        raise HTTPException(status_code=404, detail="Assemblée introuvable")
    return a


def _get_resolution(db: Session, a: models.Assemblee, resolution_id: int) -> models.Resolution:
    r = db.get(models.Resolution, resolution_id)
    if not r or r.assemblee_id != a.id:
        raise HTTPException(status_code=404, detail="Résolution introuvable")
    return r


@router.get("/assemblees")
def assemblees_list(request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(models.Assemblee).order_by(models.Assemblee.date_assemblee.desc(), models.Assemblee.id.desc())
    items = q.all()
    if not user.is_internal:  # un représentant ne voit que les assemblées convoquées ou tenues
        items = [a for a in items if a.statut != "preparation"]
    return render(request, "assemblees_list.html", user, items=items, types=models.ASSEMBLEE_TYPES,
                  modes=models.VOTE_MODES)


@router.post("/assemblees")
def assemblee_create(type: str = Form(...), date_assemblee: str = Form(...), heure: str = Form(""),
                     lieu: str = Form(...), ordre_du_jour: str = Form(...), mode_vote: str = Form("organisation"),
                     demande_age: str = Form(""), user: models.User = Depends(require_member_manager),
                     db: Session = Depends(get_db)):
    when = parse_date(date_assemblee)
    if not when:
        raise HTTPException(status_code=400, detail="Date obligatoire")
    a = gouvernance.create_assemblee(db, user, type_=type, date_assemblee=when, heure=heure.strip(), lieu=lieu,
                                     ordre_du_jour=ordre_du_jour, mode_vote=mode_vote, demande_age=demande_age)
    db.commit()
    return _redirect(f"/assemblees/{a.id}")


@router.get("/assemblees/{assemblee_id}")
def assemblee_detail(assemblee_id: int, request: Request, user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    a = _get(db, assemblee_id)
    if not user.is_internal:
        if a.statut == "preparation":
            raise HTTPException(status_code=404, detail="Assemblée introuvable")
        # Représentant : convocation uniquement (pas d'émargement ni de votes nominatifs)
        return render(request, "assemblee_convocation.html", user, a=a)
    voting = gouvernance.voting_base(db, a)
    dues = {}
    if a.statut == "en_seance" and user.can_view_finances:
        # Information seulement : jamais de blocage à l'assemblée
        for f in db.query(models.Faitiere):
            e = db.query(models.Echeance).filter_by(faitiere_id=f.id, type="annuelle",
                                                    annee=a.date_assemblee.year).first()
            dues[f.id] = e.statut if e else None
    return render(request, "assemblee_detail.html", user, a=a, voting=voting, dues=dues,
                  vote_choix=models.VOTE_CHOIX, modes=models.VOTE_MODES)


@router.post("/assemblees/{assemblee_id}/avis-ca")
def assemblee_avis(assemblee_id: int, reference: str = Form(""), user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    if user.role not in models.ADHESION_AVIS_ROLES:
        raise HTTPException(status_code=403, detail="Action non autorisée pour votre rôle")
    a = _get(db, assemblee_id)
    gouvernance.record_ca_opinion(db, user, a, reference)
    db.commit()
    return _redirect(f"/assemblees/{a.id}")


@router.post("/assemblees/{assemblee_id}/convoquer")
def assemblee_convoquer(assemblee_id: int, user: models.User = Depends(require_member_manager),
                        db: Session = Depends(get_db)):
    a = _get(db, assemblee_id)
    gouvernance.send_convocation(db, user, a)
    db.commit()
    return _redirect(f"/assemblees/{a.id}")


@router.get("/assemblees/{assemblee_id}/convocation.pdf")
def convocation_pdf(assemblee_id: int, user: models.User = Depends(require_internal), db: Session = Depends(get_db)):
    a = _get(db, assemblee_id)
    return Response(pdfs.convocation_pdf(a), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="convocation-{a.type}-{a.date_assemblee}.pdf"'})


@router.post("/assemblees/{assemblee_id}/ouvrir")
def assemblee_ouvrir(assemblee_id: int, user: models.User = Depends(require_member_manager),
                     db: Session = Depends(get_db)):
    a = _get(db, assemblee_id)
    gouvernance.open_session(db, user, a)
    db.commit()
    return _redirect(f"/assemblees/{a.id}")


@router.post("/assemblees/{assemblee_id}/emargement")
async def assemblee_emargement(assemblee_id: int, request: Request, user: models.User = Depends(require_member_manager),
                               db: Session = Depends(get_db)):
    a = _get(db, assemblee_id)
    form = await request.form()
    ids = {int(v) for v in form.getlist("present") if str(v).isdigit()}
    gouvernance.set_presence(db, user, a, ids & {p.id for p in a.presences})
    db.commit()
    return _redirect(f"/assemblees/{a.id}")


@router.post("/assemblees/{assemblee_id}/resolutions")
def resolution_create(assemblee_id: int, intitule: str = Form(...), texte: str = Form(""), regle: str = Form("majorite"),
                      user: models.User = Depends(require_member_manager), db: Session = Depends(get_db)):
    a = _get(db, assemblee_id)
    gouvernance.add_resolution(db, user, a, intitule, texte, regle)
    db.commit()
    return _redirect(f"/assemblees/{a.id}")


@router.post("/assemblees/{assemblee_id}/resolutions/{resolution_id}/votes")
async def resolution_votes(assemblee_id: int, resolution_id: int, request: Request,
                           user: models.User = Depends(require_member_manager), db: Session = Depends(get_db)):
    a = _get(db, assemblee_id)
    r = _get_resolution(db, a, resolution_id)
    form = await request.form()
    choix = {k[len("vote_"):]: str(v) for k, v in form.items() if k.startswith("vote_") and str(v)}
    gouvernance.record_votes(db, user, a, r, choix)
    db.commit()
    return _redirect(f"/assemblees/{a.id}")


@router.post("/assemblees/{assemblee_id}/resolutions/{resolution_id}/cloturer")
def resolution_cloturer(assemblee_id: int, resolution_id: int, consensus: str = Form(""),
                        user: models.User = Depends(require_member_manager), db: Session = Depends(get_db)):
    a = _get(db, assemblee_id)
    r = _get_resolution(db, a, resolution_id)
    gouvernance.close_scrutin(db, user, a, r, consensus=bool(consensus))
    db.commit()
    return _redirect(f"/assemblees/{a.id}")


@router.post("/assemblees/{assemblee_id}/cloturer")
def assemblee_cloturer(assemblee_id: int, president: str = Form(""), assesseur1: str = Form(""),
                       assesseur2: str = Form(""), user: models.User = Depends(require_member_manager),
                       db: Session = Depends(get_db)):
    a = _get(db, assemblee_id)
    gouvernance.close_assemblee(db, user, a, president, assesseur1, assesseur2)
    db.commit()
    return _redirect(f"/assemblees/{a.id}")


@router.get("/assemblees/{assemblee_id}/pv.pdf")
def minutes(assemblee_id: int, user: models.User = Depends(require_internal), db: Session = Depends(get_db)):
    a = _get(db, assemblee_id)
    if a.statut != "close":
        raise HTTPException(status_code=409, detail="Le procès-verbal n'est disponible qu'après la clôture de l'assemblée")
    return Response(pdfs.minutes_pdf(a, gouvernance.voting_base(db, a)), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="pv-{a.type}-{a.date_assemblee}.pdf"'})
