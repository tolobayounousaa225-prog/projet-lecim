"""Espace de formation : formations, sessions, inscriptions du personnel des faîtières, présence, certificats.

Le secrétariat Formation (droit de modification de la rubrique « Formation ») gère formations et sessions, marque la
présence et délivre les certificats. Une faîtière inscrit son propre personnel aux sessions ouvertes et ne voit jamais
les inscrits des autres."""

import datetime
import secrets

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from .. import formations_catalogue, models, notifier, pdfs
from ..audit import log_action
from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..rate_limit import rate_limiter
from ..web import clean, parse_date, render

router = APIRouter()
verify_limit = rate_limiter("certificat-verify", 60, 600)


def _staff_read(user: models.User) -> bool:
    return user.is_internal and user.can("formation")


def _staff_write(user: models.User) -> bool:
    return user.is_internal and user.can("formation", True)


def _need_access(user: models.User) -> None:
    if user.is_internal and not user.can("formation"):
        raise HTTPException(status_code=403, detail="Cette rubrique ne fait pas partie de votre espace")


def _need_write(user: models.User) -> None:
    if not _staff_write(user):
        raise HTTPException(status_code=403, detail="Action non autorisée pour votre rôle")


def _text(value: str, label: str, required: bool = False, limit: int = 255) -> str | None:
    v = clean(value)
    if required and not v:
        raise HTTPException(status_code=400, detail=f"{label} : champ obligatoire")
    if v and len(v) > limit:
        raise HTTPException(status_code=400, detail=f"{label} : texte trop long")
    return v


@router.get("/formations")
def formations_list(request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _need_access(user)
    q = db.query(models.Formation).order_by(models.Formation.id.desc())
    items = q.all()
    if not user.is_internal:                          # une faîtière voit les formations qui ont au moins une session proposée
        items = [f for f in items if any(s.statut in ("ouverte", "cloturee", "terminee") for s in f.sessions)]
    mine = {}
    if not user.is_internal and user.faitiere_id:
        for i in db.query(models.InscriptionFormation).filter_by(faitiere_id=user.faitiere_id).filter(models.InscriptionFormation.statut != "annule"):
            mine.setdefault(i.session_id, []).append(i)
    return render(request, "formations.html", user, items=items, can_write=_staff_write(user), mine=mine, today=datetime.date.today())


@router.post("/formations/catalogue")
def formation_catalogue(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Charge le catalogue proposé (14 formations). Les formations dont le titre existe déjà sont laissées telles quelles."""
    _need_write(user)
    have = {f.titre for f in db.query(models.Formation)}
    added = 0
    for entry in formations_catalogue.CATALOGUE:
        if entry[0] in have:
            continue
        db.add(models.Formation(titre=entry[0], public_cible=entry[1], duree=entry[2], description=formations_catalogue.description(entry)))
        added += 1
    log_action(db, user, "creation", "formations", None, f"catalogue proposé : {added} formation(s) ajoutée(s)")
    db.commit()
    return RedirectResponse("/formations", status_code=303)


@router.post("/formations")
def formation_add(titre: str = Form(""), description: str = Form(""), public_cible: str = Form(""), duree: str = Form(""),
                  user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _need_write(user)
    f = models.Formation(titre=_text(titre, "Titre", True), description=_text(description, "Description", limit=3000),
                         public_cible=_text(public_cible, "Public visé"), duree=_text(duree, "Durée", limit=60))
    db.add(f)
    db.flush()
    log_action(db, user, "creation", "formations", f.id, f.titre)
    db.commit()
    return RedirectResponse("/formations", status_code=303)


@router.post("/formations/{formation_id}/sessions")
def session_add(formation_id: int, date_debut: str = Form(""), date_fin: str = Form(""), lieu: str = Form(""), places: str = Form(""),
                limite_inscription: str = Form(""), user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _need_write(user)
    f = db.get(models.Formation, formation_id)
    if not f:
        raise HTTPException(status_code=404, detail="Formation introuvable")
    start, end = parse_date(date_debut), parse_date(date_fin)
    if not start or (end and end < start):
        raise HTTPException(status_code=400, detail="Dates invalides (la fin ne peut pas précéder le début)")
    if places.strip() and (not places.strip().isdigit() or not 1 <= int(places) <= 5000):
        raise HTTPException(status_code=400, detail="Nombre de places invalide")
    s = models.SessionFormation(formation_id=f.id, date_debut=start, date_fin=end, lieu=_text(lieu, "Lieu", True),
                                places=int(places) if places.strip() else None, limite_inscription=parse_date(limite_inscription))
    db.add(s)
    db.flush()
    log_action(db, user, "creation", "sessions_formation", s.id, f"{f.titre} — {start}")
    notifier.notify_all_faitieres(db, f"Nouvelle session de formation : {f.titre}", texte=f"{start:%d/%m/%Y} — {s.lieu}", lien=f"/formations/sessions/{s.id}", kind="formation")
    db.commit()
    return RedirectResponse(f"/formations/sessions/{s.id}", status_code=303)


def _session(db: Session, sid: int) -> models.SessionFormation:
    s = db.get(models.SessionFormation, sid)
    if not s:
        raise HTTPException(status_code=404, detail="Session introuvable")
    return s


@router.get("/formations/sessions/{session_id}")
def session_detail(session_id: int, request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _need_access(user)
    s = _session(db, session_id)
    if not user.is_internal and s.statut == "annulee":
        raise HTTPException(status_code=404, detail="Session introuvable")
    rows = s.inscriptions if user.is_internal else [i for i in s.inscriptions if i.faitiere_id == user.faitiere_id]
    faitieres = db.query(models.Faitiere).order_by(models.Faitiere.sigle).all() if _staff_write(user) else []
    return render(request, "formation_session.html", user, s=s, rows=rows, can_write=_staff_write(user), faitieres=faitieres,
                  statuts=models.SESSION_STATUTS, today=datetime.date.today())


@router.post("/formations/sessions/{session_id}/inscrire")
def enroll(session_id: int, nom: str = Form(""), fonction: str = Form(""), email: str = Form(""), telephone: str = Form(""),
           faitiere_id: str = Form(""), user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _need_access(user)
    s = _session(db, session_id)
    if user.is_internal:
        _need_write(user)
        fid = int(faitiere_id) if faitiere_id.isdigit() else None
    else:
        fid = user.faitiere_id                           # une faîtière n'inscrit que son propre personnel
    if not fid or not db.get(models.Faitiere, fid):
        raise HTTPException(status_code=400, detail="Faîtière à indiquer")
    if not s.ouverte_aux_inscriptions:
        raise HTTPException(status_code=400, detail="Les inscriptions ne sont plus ouvertes pour cette session")
    name = _text(nom, "Nom", True)
    mail = _text(email, "E-mail")
    if mail and "@" not in mail:
        raise HTTPException(status_code=400, detail="Adresse e-mail invalide")
    if any(i.faitiere_id == fid and i.nom.lower() == name.lower() and i.statut != "annule" for i in s.inscriptions):
        raise HTTPException(status_code=409, detail="Cette personne est déjà inscrite")
    i = models.InscriptionFormation(session_id=s.id, faitiere_id=fid, nom=name, fonction=_text(fonction, "Fonction", limit=120), email=mail,
                                    telephone=_text(telephone, "Téléphone", limit=40))
    db.add(i)
    db.flush()
    log_action(db, user, "inscription", "sessions_formation", s.id, f"{name} ({fid})")
    if not user.is_internal:
        notifier.notify_roles(db, {"formation"}, f"Inscription à « {s.formation.titre} »", texte=f"{name} — {i.faitiere.sigle}", lien=f"/formations/sessions/{s.id}", kind="formation")
    db.commit()
    return RedirectResponse(f"/formations/sessions/{s.id}", status_code=303)


@router.post("/formations/inscriptions/{inscription_id}/annuler")
def cancel(inscription_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _need_access(user)
    i = db.get(models.InscriptionFormation, inscription_id)
    if not i or (not user.is_internal and i.faitiere_id != user.faitiere_id):
        raise HTTPException(status_code=404, detail="Inscription introuvable")
    if user.is_internal:
        _need_write(user)
    if i.statut in ("present", "absent") or i.session.statut in ("terminee", "annulee"):
        raise HTTPException(status_code=400, detail="Cette inscription ne peut plus être annulée")
    i.statut = "annule"
    log_action(db, user, "annulation", "sessions_formation", i.session_id, i.nom)
    db.commit()
    return RedirectResponse(f"/formations/sessions/{i.session_id}", status_code=303)


@router.post("/formations/sessions/{session_id}/statut")
def set_status(session_id: int, statut: str = Form(""), user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _need_write(user)
    s = _session(db, session_id)
    if statut not in ("ouverte", "cloturee", "annulee") or s.statut == "terminee":
        raise HTTPException(status_code=400, detail="Changement de statut impossible")
    s.statut = statut
    log_action(db, user, "statut", "sessions_formation", s.id, statut)
    db.commit()
    return RedirectResponse(f"/formations/sessions/{s.id}", status_code=303)


@router.post("/formations/sessions/{session_id}/terminer")
async def finish(session_id: int, request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Enregistre la présence (cases cochées = présents) puis délivre un certificat à chaque présent."""
    _need_write(user)
    s = _session(db, session_id)
    if s.statut in ("terminee", "annulee"):
        raise HTTPException(status_code=400, detail="Session déjà terminée ou annulée")
    if s.date_debut > datetime.date.today():
        raise HTTPException(status_code=400, detail="La session n'a pas encore commencé")
    form = await request.form()
    present = {int(v) for v in form.getlist("present") if str(v).isdigit()}
    year = (s.date_fin or s.date_debut).year
    count = db.query(models.InscriptionFormation).filter(models.InscriptionFormation.certificat_numero.like(f"FORM-{year}-%")).count()
    by_faitiere: dict[int, int] = {}
    for i in s.inscriptions:
        if i.statut == "annule":
            continue
        if i.id in present:
            count += 1
            i.statut, i.certificat_numero, i.certificat_token = "present", f"FORM-{year}-{count:04d}", secrets.token_urlsafe(18)
            by_faitiere[i.faitiere_id] = by_faitiere.get(i.faitiere_id, 0) + 1
        else:
            i.statut = "absent"
    s.statut = "terminee"
    log_action(db, user, "terminer", "sessions_formation", s.id, f"{len(present)} certificat(s)")
    for fid, n in by_faitiere.items():
        notifier.notify_faitiere(db, fid, f"Certificats de formation disponibles : {s.formation.titre}", texte=f"{n} certificat(s)", lien=f"/formations/sessions/{s.id}", kind="formation")
    db.commit()
    return RedirectResponse(f"/formations/sessions/{s.id}", status_code=303)


@router.get("/formations/inscriptions/{inscription_id}/certificat.pdf")
def certificate(inscription_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _need_access(user)
    i = db.get(models.InscriptionFormation, inscription_id)
    if not i or not i.certificat_token or (not user.is_internal and i.faitiere_id != user.faitiere_id):
        raise HTTPException(status_code=404, detail="Certificat introuvable")
    url = f"{settings.public_base_url.rstrip('/')}/verifier/certificat/{i.certificat_token}"
    return Response(pdfs.formation_certificate_pdf(i, url), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="certificat-{i.certificat_numero}.pdf"', "Cache-Control": "private, no-store"})


@router.get("/verifier/certificat/{token}", dependencies=[Depends(verify_limit)])
def verify_certificate(token: str, request: Request, db: Session = Depends(get_db)):
    i = db.query(models.InscriptionFormation).filter_by(certificat_token=token).first()
    if not i:
        raise HTTPException(status_code=404, detail="Certificat non reconnu")
    return render(request, "verifier_certificat.html", None, i=i, s=i.session, f=i.session.formation)
