"""Accès par rubrique : l'administrateur règle qui voit quoi (par rôle) et fait des exceptions (par personne)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import acces, models
from ..audit import log_action
from ..database import get_db
from ..deps import require_admin
from ..web import render

router = APIRouter()

# Rôles réglables : tous les organes de la PSIE (la faîtière a son propre espace, sans rubrique)
ROLES = [r for r in models.ROLES if r != "faitiere"]


def _level(value) -> int | None:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n in acces.LEVELS else None


@router.get("/acces")
def acces_page(request: Request, user: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    matrix = {role: acces.role_defaults_with_overrides(db, role) for role in ROLES}
    defaults = {role: acces.defaults_for(role) for role in ROLES}
    return render(request, "acces_matrice.html", user, sections=acces.SECTIONS, matrix_roles=ROLES, matrix=matrix,
                  defaults=defaults, levels=acces.LEVELS, saved=bool(request.query_params.get("ok")))


@router.post("/acces")
async def acces_save(request: Request, user: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    form = await request.form()
    changes = []
    db.query(models.AccesRole).delete()
    for role in ROLES:
        base = acces.defaults_for(role)
        for section in acces.SECTIONS:
            level = _level(form.get(f"n__{role}__{section}"))
            if level is None:
                continue
            if level != base.get(section, 0):                 # on ne garde que ce qui diffère des valeurs par défaut
                db.add(models.AccesRole(role=role, section=section, niveau=level))
                changes.append(f"{role}/{section}={level}")
    log_action(db, user, "acces_roles", "acces", None, "; ".join(changes)[:500] or "valeurs par défaut")
    db.commit()
    return RedirectResponse("/acces?ok=1", status_code=303)


@router.post("/acces/reinitialiser")
def acces_reset(user: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    db.query(models.AccesRole).delete()
    log_action(db, user, "acces_roles", "acces", None, "retour aux valeurs par défaut")
    db.commit()
    return RedirectResponse("/acces?ok=1", status_code=303)


def _target(db: Session, user_id: int) -> models.User:
    target = db.get(models.User, user_id)
    if not target or target.role == "faitiere":
        raise HTTPException(status_code=404, detail="Compte introuvable ou sans rubriques à régler")
    return target


@router.get("/users/{user_id}/acces")
def user_acces_page(user_id: int, request: Request, user: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    target = _target(db, user_id)
    role_levels = acces.role_defaults_with_overrides(db, target.role)
    mine = {r.section: r.niveau for r in db.query(models.AccesUtilisateur).filter_by(user_id=target.id)}
    return render(request, "user_acces.html", user, target=target, sections=acces.SECTIONS, role_levels=role_levels,
                  mine=mine, levels=acces.LEVELS, saved=bool(request.query_params.get("ok")))


@router.post("/users/{user_id}/acces")
async def user_acces_save(user_id: int, request: Request, user: models.User = Depends(require_admin),
                          db: Session = Depends(get_db)):
    target = _target(db, user_id)
    form = await request.form()
    role_levels = acces.role_defaults_with_overrides(db, target.role)
    db.query(models.AccesUtilisateur).filter_by(user_id=target.id).delete()
    changes = []
    for section in acces.SECTIONS:
        level = _level(form.get(f"n__{section}"))
        if level is not None and level != role_levels.get(section, 0):     # vide = comme le rôle
            db.add(models.AccesUtilisateur(user_id=target.id, section=section, niveau=level))
            changes.append(f"{section}={level}")
    log_action(db, user, "acces_personne", "user", target.id, f"{target.email}: " + ("; ".join(changes) or "comme son rôle"))
    db.commit()
    return RedirectResponse(f"/users/{target.id}/acces?ok=1", status_code=303)
