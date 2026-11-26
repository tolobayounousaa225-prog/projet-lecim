"""Relation PSIE ↔ faîtières : annonces (de la PSIE vers les faîtières) et demandes (des faîtières vers la PSIE)."""

import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models
from ..audit import log_action
from ..database import get_db
from ..deps import get_current_user, require_member_manager
from ..web import clean, render

router = APIRouter()


def _need_read(user: models.User) -> None:
    if user.is_internal and not user.can("membres"):
        raise HTTPException(status_code=403, detail="Cette rubrique ne fait pas partie de votre espace")


@router.get("/annonces")
def annonces_list(request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _need_read(user)
    q = db.query(models.Annonce)
    if not user.is_internal:                                   # toutes les faîtières, ou celles qui lui sont adressées
        q = q.filter(or_(models.Annonce.faitiere_id.is_(None), models.Annonce.faitiere_id == user.faitiere_id))
    items = q.order_by(models.Annonce.id.desc()).limit(100).all()
    faitieres = db.query(models.Faitiere).order_by(models.Faitiere.sigle).all() if user.can_manage_members else []
    return render(request, "annonces.html", user, items=items, faitieres=faitieres,
                  names={f.id: f.sigle for f in db.query(models.Faitiere)})


@router.post("/annonces")
def annonce_add(titre: str = Form(""), texte: str = Form(""), cible: str = Form(""),
                user: models.User = Depends(require_member_manager), db: Session = Depends(get_db)):
    titre, texte = clean(titre), clean(texte)
    if not titre or not texte or len(titre) > 255 or len(texte) > 5000:
        raise HTTPException(status_code=400, detail="Titre et message obligatoires")
    fid = None
    if cible:
        if not cible.isdigit() or not db.get(models.Faitiere, int(cible)):
            raise HTTPException(status_code=400, detail="Faîtière inconnue")
        fid = int(cible)
    a = models.Annonce(titre=titre, texte=texte, faitiere_id=fid, auteur_id=user.id)
    db.add(a)
    db.flush()
    log_action(db, user, "creation", "annonces", a.id, titre)
    db.commit()
    return RedirectResponse("/annonces", status_code=303)


@router.post("/annonces/{annonce_id}/supprimer")
def annonce_delete(annonce_id: int, user: models.User = Depends(require_member_manager), db: Session = Depends(get_db)):
    a = db.get(models.Annonce, annonce_id)
    if not a:
        raise HTTPException(status_code=404, detail="Annonce introuvable")
    log_action(db, user, "suppression", "annonces", a.id, a.titre)
    db.delete(a)
    db.commit()
    return RedirectResponse("/annonces", status_code=303)


@router.get("/demandes")
def demandes_list(request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _need_read(user)
    q = db.query(models.DemandeFaitiere)
    if not user.is_internal:
        q = q.filter_by(faitiere_id=user.faitiere_id)
    return render(request, "demandes.html", user, items=q.order_by(models.DemandeFaitiere.id.desc()).limit(200).all(),
                  types=models.DEMANDE_TYPES, statuts=models.DEMANDE_STATUTS)


@router.post("/demandes")
def demande_add(type: str = Form(""), objet: str = Form(""), message: str = Form(""),
                user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.is_internal or not user.faitiere_id:                # seule une faîtière écrit à la PSIE
        raise HTTPException(status_code=403, detail="Action non autorisée pour votre rôle")
    objet = clean(objet)
    if type not in models.DEMANDE_TYPES or not objet or len(objet) > 255 or len(message or "") > 5000:
        raise HTTPException(status_code=400, detail="Type et objet obligatoires")
    d = models.DemandeFaitiere(faitiere_id=user.faitiere_id, type=type, objet=objet, message=clean(message))
    db.add(d)
    db.flush()
    log_action(db, user, "creation", "demandes", d.id, objet)
    db.commit()
    return RedirectResponse("/demandes", status_code=303)


@router.post("/demandes/{demande_id}/traiter")
def demande_answer(demande_id: int, statut: str = Form(""), reponse: str = Form(""),
                   user: models.User = Depends(require_member_manager), db: Session = Depends(get_db)):
    d = db.get(models.DemandeFaitiere, demande_id)
    if not d:
        raise HTTPException(status_code=404, detail="Demande introuvable")
    if statut not in models.DEMANDE_STATUTS or len(reponse or "") > 5000:
        raise HTTPException(status_code=400, detail="Statut inconnu")
    d.statut, d.reponse, d.updated_at = statut, clean(reponse), datetime.datetime.utcnow()
    log_action(db, user, "reponse", "demandes", d.id, statut)
    db.commit()
    return RedirectResponse("/demandes", status_code=303)
