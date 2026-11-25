"""Espace d'une faîtière : ses délégués régionaux et ses écoles.
Elle les tient à jour elle-même ; les organes de la PSIE (rôles internes) peuvent les consulter,
et la DEN et le secrétariat les corriger. Une faîtière ne voit jamais celles des autres."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import models
from ..audit import log_action
from ..database import get_db
from ..deps import get_current_user
from ..web import clean, render

router = APIRouter()

# type -> (modèle, champs du formulaire, titre)
KINDS = {
    "delegues": (models.DelegueRegional, ("nom", "drena", "telephone", "email"), "Délégués régionaux"),
    "ecoles": (models.Ecole, ("nom", "localite", "drena", "telephone"), "Écoles"),
}
REQUIRED = {"nom"}
LABELS = {"nom": "Nom", "drena": "DRENA", "telephone": "Téléphone", "email": "E-mail", "localite": "Localité"}


def _faitiere(db: Session, user: models.User, faitiere_id: int, write: bool = False) -> models.Faitiere:
    f = db.get(models.Faitiere, faitiere_id)
    if not f or not user.can_view_faitiere(faitiere_id):
        raise HTTPException(status_code=404, detail="Faîtière introuvable")   # même réponse : on ne révèle rien
    if write and not (user.faitiere_id == faitiere_id or user.can_manage_members):
        raise HTTPException(status_code=403, detail="Action non autorisée pour votre rôle")
    return f


def _kind(kind: str):
    if kind not in KINDS:
        raise HTTPException(status_code=404, detail="Rubrique introuvable")
    return KINDS[kind]


def _fields(kind: str, form: dict) -> dict:
    values = {name: clean(form.get(name)) for name in KINDS[kind][1]}
    for name in REQUIRED:
        if not values.get(name):
            raise HTTPException(status_code=400, detail=f"{LABELS[name]} : champ obligatoire")
    for name, value in values.items():
        if value and len(value) > 255:
            raise HTTPException(status_code=400, detail=f"{LABELS[name]} : texte trop long")
    return values


@router.get("/faitieres/{faitiere_id}/{kind}")
def space_list(faitiere_id: int, kind: str, request: Request, user: models.User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    model, fields, title = _kind(kind)
    f = _faitiere(db, user, faitiere_id)
    items = db.query(model).filter_by(faitiere_id=faitiere_id).order_by(model.id).all()
    can_write = user.faitiere_id == faitiere_id or user.can_manage_members
    return render(request, "espace_liste.html", user, f=f, kind=kind, title=title, fields=fields, labels=LABELS,
                  items=items, can_write=can_write, edit=None)


@router.post("/faitieres/{faitiere_id}/{kind}")
def space_add(faitiere_id: int, kind: str, nom: str = Form(""), drena: str = Form(""), localite: str = Form(""),
              telephone: str = Form(""), email: str = Form(""), user: models.User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    model, fields, _ = _kind(kind)
    _faitiere(db, user, faitiere_id, write=True)
    values = _fields(kind, {"nom": nom, "drena": drena, "localite": localite, "telephone": telephone, "email": email})
    if kind == "delegues" and not values.get("drena"):
        raise HTTPException(status_code=400, detail="DRENA : champ obligatoire")
    item = model(faitiere_id=faitiere_id, **values)
    db.add(item)
    db.flush()
    log_action(db, user, "creation", kind, item.id, values["nom"])
    db.commit()
    return RedirectResponse(f"/faitieres/{faitiere_id}/{kind}", status_code=303)


@router.post("/faitieres/{faitiere_id}/{kind}/{item_id}/supprimer")
def space_delete(faitiere_id: int, kind: str, item_id: int, user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    model, _, _ = _kind(kind)
    _faitiere(db, user, faitiere_id, write=True)
    item = db.get(model, item_id)
    if not item or item.faitiere_id != faitiere_id:                       # jamais l'élément d'une autre faîtière
        raise HTTPException(status_code=404, detail="Élément introuvable")
    log_action(db, user, "suppression", kind, item.id, item.nom)
    db.delete(item)
    db.commit()
    return RedirectResponse(f"/faitieres/{faitiere_id}/{kind}", status_code=303)
