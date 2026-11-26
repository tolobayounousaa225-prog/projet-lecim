"""Membres : pièces justificatives, registre légal, historique des mandats, gestion des comptes."""

import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import media, models, password_reset, pdfs
from ..audit import log_action
from ..config import settings
from ..database import get_db
from ..deps import get_current_user, require_admin, require_internal, require_member_manager
from ..emailing import send_email
from ..web import clean, render
from .admin import _check_mandat, _get_faitiere_for, _mandat_from_form  # noqa: F401

router = APIRouter()

MAX_REQUEST_BYTES = 20 * 1024 * 1024


def _back(next_url: str, default: str) -> RedirectResponse:
    return RedirectResponse(next_url if next_url.startswith("/") and not next_url.startswith("//") else default,
                            status_code=303)


# ---------- Pièces justificatives d'un membre ----------

@router.post("/faitieres/{faitiere_id}/pieces")
async def piece_upload(faitiere_id: int, request: Request, user: models.User = Depends(require_member_manager),
                       db: Session = Depends(get_db)):
    faitiere = _get_faitiere_for(user, faitiere_id, db)
    if int(request.headers.get("content-length") or 0) > MAX_REQUEST_BYTES:
        raise HTTPException(status_code=413, detail="Envoi trop volumineux")
    form = await request.form()
    kind = str(form.get("type", ""))
    upload = form.get("fichier")
    if kind not in models.MEMBRE_PIECE_TYPES:
        raise HTTPException(status_code=400, detail="Type de pièce invalide")
    if upload is None or isinstance(upload, str) or not upload.filename:
        raise HTTPException(status_code=400, detail="Choisissez un fichier")
    raw = await upload.read()
    try:
        # PDF ou image : même nettoyage que pour le site (en-tête vérifié, image ré-encodée sans métadonnées)
        data, mime, ext, _ = media.process(raw, "pdf" if raw.startswith(b"%PDF-") else "image")
    except media.MediaError as e:
        raise HTTPException(status_code=400, detail=str(e))
    piece = models.PieceFaitiere(faitiere_id=faitiere.id, type=kind, nom=media.safe_name(upload.filename), mime=mime,
                                 extension=ext, taille=len(data), contenu=data, created_by_id=user.id)
    db.add(piece)
    db.flush()
    log_action(db, user, "creation", "piece", piece.id, f"{faitiere.sigle} — {kind} — {piece.nom}")
    db.commit()
    return RedirectResponse(f"/faitieres/{faitiere.id}", status_code=303)


@router.get("/pieces/{piece_id}")
def piece_download(piece_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    piece = db.get(models.PieceFaitiere, piece_id)
    if not piece or not user.can_view_faitiere(piece.faitiere_id):
        raise HTTPException(status_code=404, detail="Pièce introuvable")
    return Response(piece.contenu, media_type=piece.mime,
                    headers={"Content-Disposition": f'attachment; filename="{piece.nom}"', "Cache-Control": "private, no-store"})


@router.post("/pieces/{piece_id}/supprimer")
def piece_delete(piece_id: int, user: models.User = Depends(require_member_manager), db: Session = Depends(get_db)):
    piece = db.get(models.PieceFaitiere, piece_id)
    if not piece:
        raise HTTPException(status_code=404, detail="Pièce introuvable")
    fid = piece.faitiere_id
    log_action(db, user, "suppression", "piece", piece.id, f"{piece.type} — {piece.nom}")
    db.delete(piece)
    db.commit()
    return RedirectResponse(f"/faitieres/{fid}", status_code=303)


# ---------- Registre des membres (PDF) ----------

@router.get("/registre-membres.pdf")
def registre_membres(user: models.User = Depends(require_internal), db: Session = Depends(get_db)):
    items = db.query(models.Faitiere).order_by(models.Faitiere.categorie, models.Faitiere.sigle).all()
    log_action(db, user, "edition", "registre_membres", None, f"{len(items)} organisations")
    db.commit()
    return Response(pdfs.registre_membres_pdf(items), media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="registre-des-membres.pdf"',
                             "Cache-Control": "private, no-store"})


# ---------- Mandats : mettre fin (l'historique est conservé), corriger ----------

@router.post("/mandats/{mandat_id}/terminer")
def mandat_end(mandat_id: int, date_fin: str = Form(""), next: str = Form("/mandats"),
               user: models.User = Depends(require_member_manager), db: Session = Depends(get_db)):
    """Met fin à un mandat sans le supprimer : chaque désignation reste conservée (cahier des charges, 4.1)."""
    mandat = db.get(models.Mandat, mandat_id)
    if not mandat:
        raise HTTPException(status_code=404, detail="Mandat introuvable")
    from ..web import parse_date
    fin = parse_date(date_fin) or datetime.date.today()
    if mandat.date_debut and fin < mandat.date_debut:
        raise HTTPException(status_code=400, detail="La fin du mandat précède son début")
    mandat.date_fin = fin
    log_action(db, user, "fin_mandat", "mandat", mandat.id, f"{mandat.organe} — {mandat.full_name} — {fin}")
    db.commit()
    return _back(next, "/mandats")


@router.get("/mandats/{mandat_id}/edit")
def mandat_edit_form(mandat_id: int, request: Request, user: models.User = Depends(require_member_manager),
                     db: Session = Depends(get_db)):
    mandat = db.get(models.Mandat, mandat_id)
    if not mandat:
        raise HTTPException(status_code=404, detail="Mandat introuvable")
    return render(request, "mandat_form.html", user, m=mandat,
                  faitieres=db.query(models.Faitiere).order_by(models.Faitiere.sigle).all())


@router.post("/mandats/{mandat_id}/edit")
def mandat_edit(mandat_id: int, organe: str = Form(...), fonction: str = Form(""), full_name: str = Form(...),
                email: str = Form(""), telephone: str = Form(""), date_debut: str = Form(""), date_fin: str = Form(""),
                faitiere_id: str = Form(""), user: models.User = Depends(require_member_manager),
                db: Session = Depends(get_db)):
    mandat = db.get(models.Mandat, mandat_id)
    if not mandat:
        raise HTTPException(status_code=404, detail="Mandat introuvable")
    fid = int(faitiere_id) if faitiere_id.strip().isdigit() else None
    new = _mandat_from_form(organe, fonction, full_name, email, telephone, date_debut, date_fin, fid, db)
    for field in ("faitiere_id", "organe", "fonction", "full_name", "email", "telephone", "date_debut", "date_fin"):
        setattr(mandat, field, getattr(new, field))
    log_action(db, user, "modification", "mandat", mandat.id, f"{mandat.organe} — {mandat.full_name}")
    db.commit()
    return RedirectResponse(f"/faitieres/{mandat.faitiere_id}" if mandat.faitiere_id else "/mandats", status_code=303)


# ---------- Comptes : corriger, envoyer un lien de réinitialisation ----------

@router.get("/users/{user_id}/edit")
def user_edit_form(user_id: int, request: Request, user: models.User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    target = db.get(models.User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    return render(request, "user_form.html", user, target=target)


@router.post("/users/{user_id}/edit")
def user_edit(user_id: int, full_name: str = Form(...), email: str = Form(...), user: models.User = Depends(require_admin),
              db: Session = Depends(get_db)):
    target = db.get(models.User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    name, mail = full_name.strip(), email.strip().lower()
    if not name or "@" not in mail or " " in mail:
        raise HTTPException(status_code=400, detail="Nom et adresse e-mail valides obligatoires")
    target.full_name, target.email = name, mail
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Cette adresse e-mail est déjà utilisée")
    log_action(db, user, "modification", "user", target.id, target.email)
    db.commit()
    return RedirectResponse("/users", status_code=303)


@router.post("/users/{user_id}/lien-mdp")
def user_send_reset_link(user_id: int, user: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    """L'administrateur envoie à la personne un lien pour choisir elle-même son mot de passe
    (il n'a ainsi jamais à connaître ni à transmettre le mot de passe)."""
    target = db.get(models.User, user_id)
    if not target or not target.is_active:
        raise HTTPException(status_code=404, detail="Compte introuvable ou désactivé")
    token = password_reset.issue(db, target)
    if not token:
        raise HTTPException(status_code=429, detail="Un lien vient d'être envoyé à cette personne : patientez 2 minutes")
    link = f"{settings.public_base_url.rstrip('/')}/mot-de-passe-oublie/{token}"
    sent = send_email(
        target.email, "PSIE — Choisissez votre mot de passe",
        f"Bonjour {target.full_name},\n\nUn compte PSIE a été préparé pour vous. Pour choisir votre mot de passe, "
        f"ouvrez ce lien (valable 1 heure, à usage unique) :\n{link}\n\n"
        f"مرحبا {target.full_name}، لاختيار كلمة المرور افتحوا هذا الرابط (صالح لمدة ساعة ولمرة واحدة):\n{link}\n",
    )
    log_action(db, user, "lien_mdp_envoye", "user", target.id, target.email)
    db.commit()
    if not sent:
        raise HTTPException(status_code=503, detail="Le message n'a pas pu être envoyé (e-mail indisponible)")
    return RedirectResponse("/users?lien=1", status_code=303)


def last_logins(db: Session) -> dict[int, datetime.datetime]:
    rows = (db.query(models.AuditLog.user_id, func.max(models.AuditLog.created_at))
            .filter(models.AuditLog.action == "connexion").group_by(models.AuditLog.user_id).all())
    return {uid: when for uid, when in rows if uid is not None}
