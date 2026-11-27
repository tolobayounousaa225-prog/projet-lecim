"""Module 4 : documents de la PSIE, courrier arrivée/départ, circuit d'approbation des conventions.

Rubrique d'accès « documents » : lecture pour consulter, modification pour déposer ou saisir. Le circuit des
conventions suit les Statuts : le DEN (ou son secrétariat) prépare, le Conseil d'Administration donne son avis,
le DEN signe. L'avis du CA et la signature restent liés au rôle et ne se délèguent pas par la grille d'accès."""

import datetime
import hashlib

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import media, models, notifier, pdfs
from ..audit import log_action
from ..database import get_db
from ..deps import get_current_user, require_internal, require_write
from ..web import clean, parse_date, render

router = APIRouter()
require_docs_write = require_write("documents")
MAX_BYTES = 16 * 1024 * 1024


def _read(user: models.User = Depends(require_internal)) -> models.User:
    if not user.can("documents"):
        raise HTTPException(status_code=403, detail="Cette rubrique ne fait pas partie de votre espace")
    return user


def _text(value: str, label: str, required: bool = False, limit: int = 255) -> str | None:
    v = clean(value)
    if required and not v:
        raise HTTPException(status_code=400, detail=f"{label} : champ obligatoire")
    if v and len(v) > limit:
        raise HTTPException(status_code=400, detail=f"{label} : texte trop long")
    return v


async def _file(upload: UploadFile | None, required: bool = False):
    """Fichier nettoyé (PDF vérifié ou image ré-encodée) -> (contenu, mime, nom, sha256) ou None."""
    if upload is None or not upload.filename:
        if required:
            raise HTTPException(status_code=400, detail="Choisissez un fichier")
        return None
    raw = await upload.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (16 Mo au maximum)")
    try:
        data, mime, _, digest = media.process(raw, "pdf" if raw.startswith(b"%PDF-") else "image")
    except media.MediaError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return data, mime, media.safe_name(upload.filename), digest


def _send(content: bytes, mime: str, name: str) -> Response:
    return Response(content, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{name}"',
                                                       "Cache-Control": "private, no-store"})


# ---------------------------------------------------------------- Documents

@router.get("/documents")
def documents_list(request: Request, categorie: str = "", q: str = "", user: models.User = Depends(_read),
                   db: Session = Depends(get_db)):
    query = db.query(models.Document)
    if not user.can("documents", True):                       # les documents restreints sont réservés à ceux qui modifient
        query = query.filter(models.Document.restreint.is_(False))
    if categorie in models.DOC_CATEGORIES:
        query = query.filter_by(categorie=categorie)
    if q.strip():
        query = query.filter(models.Document.titre.ilike(f"%{q.strip()[:80]}%"))
    return render(request, "documents.html", user, items=query.order_by(models.Document.id.desc()).limit(300).all(),
                  cats=models.DOC_CATEGORIES, categorie=categorie, q=q, can_write=user.can("documents", True))


@router.post("/documents")
async def document_add(titre: str = Form(""), categorie: str = Form("autre"), description: str = Form(""),
                       restreint: str = Form(""), fichier: UploadFile | None = File(None),
                       user: models.User = Depends(require_docs_write), db: Session = Depends(get_db)):
    if categorie not in models.DOC_CATEGORIES:
        raise HTTPException(status_code=400, detail="Catégorie inconnue")
    data, mime, name, digest = await _file(fichier, required=True)
    d = models.Document(titre=_text(titre, "Titre", True), categorie=categorie, description=_text(description, "Description", limit=2000),
                        restreint=bool(restreint), nom=name, mime=mime, taille=len(data), sha256=digest, contenu=data, auteur_id=user.id)
    db.add(d)
    db.flush()
    log_action(db, user, "creation", "documents", d.id, d.titre)
    db.commit()
    return RedirectResponse("/documents", status_code=303)


def _doc(db: Session, user: models.User, doc_id: int) -> models.Document:
    d = db.get(models.Document, doc_id)
    if not d or (d.restreint and not user.can("documents", True)):
        raise HTTPException(status_code=404, detail="Document introuvable")
    return d


@router.get("/documents/{doc_id}/fichier")
def document_file(doc_id: int, user: models.User = Depends(_read), db: Session = Depends(get_db)):
    d = _doc(db, user, doc_id)
    log_action(db, user, "consultation", "documents", d.id, d.titre)
    db.commit()
    return _send(d.contenu, d.mime, d.nom)


@router.post("/documents/{doc_id}/supprimer")
def document_delete(doc_id: int, user: models.User = Depends(require_docs_write), db: Session = Depends(get_db)):
    d = _doc(db, user, doc_id)
    log_action(db, user, "suppression", "documents", d.id, d.titre)
    db.delete(d)
    db.commit()
    return RedirectResponse("/documents", status_code=303)


# ---------------------------------------------------------------- Courrier

def _next_numero(db: Session, sens: str, year: int) -> str:
    prefix = ("ARR" if sens == "arrivee" else "DEP") + f"-{year}-"
    n = db.query(func.count(models.Courrier.id)).filter(models.Courrier.numero.like(prefix + "%")).scalar() or 0
    return f"{prefix}{n + 1:04d}"


@router.get("/courrier")
def courrier_list(request: Request, sens: str = "", statut: str = "", user: models.User = Depends(_read),
                  db: Session = Depends(get_db)):
    q = db.query(models.Courrier)
    if sens in models.COURRIER_SENS:
        q = q.filter_by(sens=sens)
    if statut in models.COURRIER_STATUTS:
        q = q.filter_by(statut=statut)
    items = q.order_by(models.Courrier.id.desc()).limit(300).all()
    late = db.query(models.Courrier).filter(models.Courrier.statut.in_(("recu", "en_traitement")),
                                            models.Courrier.echeance < datetime.date.today()).count()
    return render(request, "courrier.html", user, items=items, sens=sens, statut=statut, late=late, today=datetime.date.today(),
                  sens_list=models.COURRIER_SENS, statuts=models.COURRIER_STATUTS, can_write=user.can("documents", True),
                  staff=db.query(models.User).filter(models.User.role.in_(models.INTERNAL_ROLES)).order_by(models.User.full_name).all())


@router.post("/courrier")
async def courrier_add(sens: str = Form(""), date_courrier: str = Form(""), correspondant: str = Form(""), objet: str = Form(""),
                       reference_externe: str = Form(""), responsable_id: str = Form(""), echeance: str = Form(""),
                       reponse_a_id: str = Form(""), note: str = Form(""), fichier: UploadFile | None = File(None),
                       user: models.User = Depends(require_docs_write), db: Session = Depends(get_db)):
    if sens not in models.COURRIER_SENS:
        raise HTTPException(status_code=400, detail="Sens du courrier inconnu")
    day = parse_date(date_courrier) or datetime.date.today()
    resp = int(responsable_id) if responsable_id.isdigit() and db.get(models.User, int(responsable_id)) else None
    parent = db.get(models.Courrier, int(reponse_a_id)) if reponse_a_id.isdigit() else None
    f = await _file(fichier)
    for _ in range(3):                                         # deux saisies simultanées : on retente avec le numéro suivant
        c = models.Courrier(sens=sens, numero=_next_numero(db, sens, day.year), date_courrier=day,
                            correspondant=_text(correspondant, "Correspondant", True), objet=_text(objet, "Objet", True),
                            reference_externe=_text(reference_externe, "Référence", limit=120), statut="recu" if sens == "arrivee" else "traite",
                            responsable_id=resp, echeance=parse_date(echeance), reponse_a_id=parent.id if parent else None,
                            note=_text(note, "Note", limit=3000), created_by_id=user.id)
        if f:
            c.contenu, c.mime, c.nom = f[0], f[1], f[2]
        db.add(c)
        try:
            db.flush()
            break
        except Exception:
            db.rollback()
    else:
        raise HTTPException(status_code=409, detail="Numérotation en cours : réessayez")
    if parent and parent.statut in ("recu", "en_traitement"):
        parent.statut = "traite"                               # une réponse enregistrée clôt le courrier d'origine
    if resp:
        notifier.notify(db, [db.get(models.User, resp)], f"Courrier à traiter : {c.numero}", texte=c.objet, lien=f"/courrier/{c.id}", kind="courrier", exclude_id=user.id)
    log_action(db, user, "creation", "courrier", c.id, f"{c.numero} — {c.objet}")
    db.commit()
    return RedirectResponse(f"/courrier/{c.id}", status_code=303)


@router.get("/courrier/{courrier_id}")
def courrier_detail(courrier_id: int, request: Request, user: models.User = Depends(_read), db: Session = Depends(get_db)):
    c = db.get(models.Courrier, courrier_id)
    if not c:
        raise HTTPException(status_code=404, detail="Courrier introuvable")
    replies = db.query(models.Courrier).filter_by(reponse_a_id=c.id).all()
    parent = db.get(models.Courrier, c.reponse_a_id) if c.reponse_a_id else None
    return render(request, "courrier_detail.html", user, c=c, replies=replies, parent=parent, statuts=models.COURRIER_STATUTS,
                  can_write=user.can("documents", True), has_file=bool(c.nom),
                  staff=db.query(models.User).filter(models.User.role.in_(models.INTERNAL_ROLES)).order_by(models.User.full_name).all())


@router.post("/courrier/{courrier_id}/suivi")
def courrier_follow(courrier_id: int, statut: str = Form(""), responsable_id: str = Form(""), echeance: str = Form(""),
                    note: str = Form(""), user: models.User = Depends(require_docs_write), db: Session = Depends(get_db)):
    c = db.get(models.Courrier, courrier_id)
    if not c:
        raise HTTPException(status_code=404, detail="Courrier introuvable")
    if statut not in models.COURRIER_STATUTS:
        raise HTTPException(status_code=400, detail="Statut inconnu")
    c.statut = statut
    previous = c.responsable_id
    c.responsable_id = int(responsable_id) if responsable_id.isdigit() and db.get(models.User, int(responsable_id)) else None
    if c.responsable_id and c.responsable_id != previous:
        notifier.notify(db, [db.get(models.User, c.responsable_id)], f"Courrier à traiter : {c.numero}", texte=c.objet, lien=f"/courrier/{c.id}", kind="courrier", exclude_id=user.id)
    c.echeance, c.note = parse_date(echeance), _text(note, "Note", limit=3000)
    log_action(db, user, "suivi", "courrier", c.id, f"{c.numero} → {statut}")
    db.commit()
    return RedirectResponse(f"/courrier/{c.id}", status_code=303)


@router.get("/courrier/{courrier_id}/fichier")
def courrier_file(courrier_id: int, user: models.User = Depends(_read), db: Session = Depends(get_db)):
    c = db.get(models.Courrier, courrier_id)
    if not c or not c.nom:
        raise HTTPException(status_code=404, detail="Pièce introuvable")
    return _send(c.contenu, c.mime, c.nom)


# ---------------------------------------------------------------- Conventions (circuit d'approbation)

@router.get("/conventions")
def conventions_list(request: Request, user: models.User = Depends(_read), db: Session = Depends(get_db)):
    return render(request, "conventions.html", user, items=db.query(models.Convention).order_by(models.Convention.id.desc()).all(),
                  can_write=user.can("documents", True))


@router.post("/conventions")
async def convention_add(titre: str = Form(""), partenaire: str = Form(""), objet: str = Form(""), montant: str = Form(""),
                         date_debut: str = Form(""), date_fin: str = Form(""), fichier: UploadFile | None = File(None),
                         user: models.User = Depends(require_docs_write), db: Session = Depends(get_db)):
    if montant and (not montant.strip().isdigit() or int(montant) > 10**12):
        raise HTTPException(status_code=400, detail="Montant : nombre entier attendu")
    c = models.Convention(titre=_text(titre, "Titre", True), partenaire=_text(partenaire, "Partenaire", True),
                          objet=_text(objet, "Objet", limit=3000), montant=int(montant) if montant.strip() else None,
                          date_debut=parse_date(date_debut), date_fin=parse_date(date_fin), created_by_id=user.id)
    f = await _file(fichier)
    if f:
        c.contenu, c.mime, c.nom = f[0], f[1], f[2]
    db.add(c)
    db.flush()
    db.add(models.ConventionEtape(convention_id=c.id, action="creation", par=user.full_name, role=user.role))
    log_action(db, user, "creation", "conventions", c.id, c.titre)
    db.commit()
    return RedirectResponse(f"/conventions/{c.id}", status_code=303)


def _convention(db: Session, convention_id: int) -> models.Convention:
    c = db.get(models.Convention, convention_id)
    if not c:
        raise HTTPException(status_code=404, detail="Convention introuvable")
    return c


@router.get("/conventions/{convention_id}")
def convention_detail(convention_id: int, request: Request, user: models.User = Depends(_read), db: Session = Depends(get_db)):
    c = _convention(db, convention_id)
    return render(request, "convention_detail.html", user, c=c, has_file=bool(c.nom), fcfa=lambda n: f"{n:,}".replace(",", " ") + " FCFA",
                  can_prepare=user.can("documents", True) and c.statut in ("brouillon", "rejetee"),
                  can_opine=user.role == "administrateur_ca" and c.statut == "soumise",
                  can_sign=user.role == "den" and c.statut == "approuvee")


# action -> (statut avant autorisé, statut après, rôle exigé ou None = droit de modification de la rubrique)
CIRCUIT = {
    "soumettre": (("brouillon", "rejetee"), "soumise", None),
    "avis_favorable": (("soumise",), "approuvee", "administrateur_ca"),
    "avis_defavorable": (("soumise",), "rejetee", "administrateur_ca"),
}


@router.post("/conventions/{convention_id}/action")
def convention_action(convention_id: int, action: str = Form(""), commentaire: str = Form(""),
                      user: models.User = Depends(_read), db: Session = Depends(get_db)):
    c = _convention(db, convention_id)
    if action not in CIRCUIT:
        raise HTTPException(status_code=400, detail="Action inconnue")
    before, after, role = CIRCUIT[action]
    if role is not None and user.role != role:
        raise HTTPException(status_code=403, detail="Action réservée à la fonction prévue par les Statuts")
    if role is None and not user.can("documents", True):
        raise HTTPException(status_code=403, detail="Action non autorisée pour votre rôle")
    if c.statut not in before:
        raise HTTPException(status_code=400, detail="Cette étape n'est pas possible dans l'état actuel de la convention")
    note = _text(commentaire, "Commentaire", action == "avis_defavorable", 2000)
    c.statut = after
    db.add(models.ConventionEtape(convention_id=c.id, action=action, par=user.full_name, role=user.role, commentaire=note))
    log_action(db, user, action, "conventions", c.id, f"{c.titre} → {after}")
    link = f"/conventions/{c.id}"
    if action == "soumettre":
        notifier.notify_roles(db, {"administrateur_ca"}, f"Convention à examiner : {c.titre}", texte=f"Partenaire : {c.partenaire}", lien=link, kind="convention", exclude_id=user.id)
    elif action in ("avis_favorable", "avis_defavorable"):
        who = [db.get(models.User, c.created_by_id)] if c.created_by_id else []
        who += db.query(models.User).filter_by(role="den", is_active=True).all()
        notifier.notify(db, who, f"Avis du CA sur la convention : {c.titre}", texte=c.statut_label, lien=link, kind="convention", exclude_id=user.id)
    elif action == "signer":
        notifier.notify(db, [db.get(models.User, c.created_by_id)] if c.created_by_id else [], f"Convention signée : {c.titre}", lien=link, kind="convention", exclude_id=user.id)
    db.commit()
    return RedirectResponse(f"/conventions/{c.id}", status_code=303)


@router.get("/conventions/{convention_id}/fichier")
def convention_file(convention_id: int, user: models.User = Depends(_read), db: Session = Depends(get_db)):
    c = _convention(db, convention_id)
    if not c.nom:
        raise HTTPException(status_code=404, detail="Pièce introuvable")
    return _send(c.contenu, c.mime, c.nom)
