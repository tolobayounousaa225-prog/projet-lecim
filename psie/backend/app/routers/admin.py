import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import finance, gouvernance, models
from ..audit import log_action
from ..database import get_db
from ..deps import get_current_user, require_admin, require_internal, require_member_manager
from ..security import hash_password, password_policy_error
from ..web import clean, parse_date, render

router = APIRouter()


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


# ---------- Tableau de bord ----------

@router.get("/admin")
def dashboard(request: Request, user: models.User = Depends(require_internal), db: Session = Depends(get_db)):
    faitieres = db.query(models.Faitiere).all()
    mandats = db.query(models.Mandat).all()
    sit = finance.situation(db, datetime.date.today().year) if user.can_view_finances else None
    return render(
        request,
        "dashboard.html",
        user,
        total=len(faitieres),
        actifs=sum(1 for f in faitieres if f.is_membre_actif),
        par_categorie={k: sum(1 for f in faitieres if f.categorie == k) for k in models.CATEGORIES},
        expirent=[m for m in mandats if m.echeance == "bientot"],
        expires=[m for m in mandats if m.echeance == "expire"],
        sit=sit,
        fcfa=finance.fcfa,
        composition=gouvernance.composition_organes(db),
    )


# ---------- Membres (faîtières) ----------

@router.get("/faitieres")
def faitieres_list(request: Request, user: models.User = Depends(require_internal), db: Session = Depends(get_db)):
    items = db.query(models.Faitiere).order_by(models.Faitiere.categorie, models.Faitiere.sigle).all()
    return render(request, "faitieres_list.html", user, items=items)


@router.get("/faitieres/new")
def faitiere_new(request: Request, user: models.User = Depends(require_member_manager)):
    return render(request, "faitiere_form.html", user, item=None)


def _faitiere_fields(
    nom: str, sigle: str, categorie: str, statut: str, date_creation: str, date_adhesion: str,
    statut_juridique: str, siege: str, email: str, telephone: str, notes: str,
) -> dict:
    if categorie not in models.CATEGORIES:
        raise HTTPException(status_code=400, detail="Catégorie invalide")
    if statut not in models.STATUTS_MEMBRE:
        raise HTTPException(status_code=400, detail="Statut invalide")
    if not nom.strip() or not sigle.strip():
        raise HTTPException(status_code=400, detail="Nom et sigle obligatoires")
    return dict(
        nom=nom.strip(), sigle=sigle.strip().upper(), categorie=categorie, statut=statut,
        date_creation=parse_date(date_creation), date_adhesion=parse_date(date_adhesion),
        statut_juridique=clean(statut_juridique), siege=clean(siege), email=clean(email),
        telephone=clean(telephone), notes=clean(notes),
    )


@router.post("/faitieres/new")
def faitiere_create(
    nom: str = Form(...), sigle: str = Form(...), categorie: str = Form("ordinaire"), statut: str = Form("actif"),
    date_creation: str = Form(""), date_adhesion: str = Form(""), statut_juridique: str = Form(""),
    siege: str = Form(""), email: str = Form(""), telephone: str = Form(""), notes: str = Form(""),
    user: models.User = Depends(require_member_manager), db: Session = Depends(get_db),
):
    fields = _faitiere_fields(nom, sigle, categorie, statut, date_creation, date_adhesion,
                              statut_juridique, siege, email, telephone, notes)
    item = models.Faitiere(**fields)
    db.add(item)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ce sigle existe déjà")
    log_action(db, user, "creation", "faitiere", item.id, item.sigle)
    db.commit()
    return _redirect(f"/faitieres/{item.id}")


def _get_faitiere_for(user: models.User, faitiere_id: int, db: Session) -> models.Faitiere:
    # Même réponse 404 qu'une fiche inexistante : un représentant ne doit pas pouvoir
    # deviner quelles autres faîtières existent.
    item = db.get(models.Faitiere, faitiere_id)
    if not item or not user.can_view_faitiere(faitiere_id):
        raise HTTPException(status_code=404, detail="Faîtière introuvable")
    return item


@router.get("/faitieres/{faitiere_id}")
def faitiere_detail(faitiere_id: int, request: Request, user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    item = _get_faitiere_for(user, faitiere_id, db)
    # Cotisations visibles par les organes de finances/contrôle et par la faîtière elle-même
    show_dues = user.can_view_finances or not user.is_internal
    echeances = (
        db.query(models.Echeance).filter_by(faitiere_id=item.id).order_by(models.Echeance.annee.desc()).all()
        if show_dues else []
    )
    return render(request, "faitiere_detail.html", user, item=item, show_dues=show_dues,
                  echeances=echeances, fcfa=finance.fcfa)


@router.get("/faitieres/{faitiere_id}/edit")
def faitiere_edit(faitiere_id: int, request: Request, user: models.User = Depends(require_member_manager),
                  db: Session = Depends(get_db)):
    item = _get_faitiere_for(user, faitiere_id, db)
    return render(request, "faitiere_form.html", user, item=item)


@router.post("/faitieres/{faitiere_id}/edit")
def faitiere_update(
    faitiere_id: int,
    nom: str = Form(...), sigle: str = Form(...), categorie: str = Form("ordinaire"), statut: str = Form("actif"),
    date_creation: str = Form(""), date_adhesion: str = Form(""), statut_juridique: str = Form(""),
    siege: str = Form(""), email: str = Form(""), telephone: str = Form(""), notes: str = Form(""),
    user: models.User = Depends(require_member_manager), db: Session = Depends(get_db),
):
    item = _get_faitiere_for(user, faitiere_id, db)
    fields = _faitiere_fields(nom, sigle, categorie, statut, date_creation, date_adhesion,
                              statut_juridique, siege, email, telephone, notes)
    changes = [f"{k}: {getattr(item, k)!r} -> {v!r}" for k, v in fields.items() if getattr(item, k) != v]
    for k, v in fields.items():
        setattr(item, k, v)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ce sigle existe déjà")
    log_action(db, user, "modification", "faitiere", item.id, "; ".join(changes) or "aucun changement")
    db.commit()
    return _redirect(f"/faitieres/{item.id}")


# ---------- Mandats ----------

def _check_mandat(organe: str, faitiere_id: int | None, db: Session) -> None:
    if organe not in models.ORGANES:
        raise HTTPException(status_code=400, detail="Organe invalide")
    if faitiere_id is not None and not db.get(models.Faitiere, faitiere_id):
        raise HTTPException(status_code=400, detail="Faîtière inconnue")


def _mandat_from_form(
    organe, fonction, full_name, email, telephone, date_debut, date_fin, faitiere_id, db
) -> models.Mandat:
    _check_mandat(organe, faitiere_id, db)
    if not full_name.strip():
        raise HTTPException(status_code=400, detail="Nom obligatoire")
    debut, fin = parse_date(date_debut), parse_date(date_fin)
    if debut and not fin:
        # Durée statutaire de 3 ans proposée par défaut (Statuts art. 21 et 28)
        try:
            fin = debut.replace(year=debut.year + models.MANDAT_DUREE_ANS)
        except ValueError:  # 29 février
            fin = debut.replace(year=debut.year + models.MANDAT_DUREE_ANS, day=28)
    if debut and fin and fin < debut:
        raise HTTPException(status_code=400, detail="La fin du mandat précède son début")
    return models.Mandat(
        faitiere_id=faitiere_id, organe=organe, fonction=clean(fonction), full_name=full_name.strip(),
        email=clean(email), telephone=clean(telephone), date_debut=debut, date_fin=fin,
    )


@router.get("/mandats")
def mandats_list(request: Request, user: models.User = Depends(require_internal), db: Session = Depends(get_db)):
    items = db.query(models.Mandat).order_by(models.Mandat.organe, models.Mandat.full_name).all()
    faitieres = db.query(models.Faitiere).order_by(models.Faitiere.sigle).all()
    return render(request, "mandats_list.html", user, items=items, faitieres=faitieres)


@router.post("/mandats")
def mandat_create(
    organe: str = Form(...), fonction: str = Form(""), full_name: str = Form(...), email: str = Form(""),
    telephone: str = Form(""), date_debut: str = Form(""), date_fin: str = Form(""),
    faitiere_id: str = Form(""), next: str = Form("/mandats"),
    user: models.User = Depends(require_member_manager), db: Session = Depends(get_db),
):
    fid = int(faitiere_id) if faitiere_id.strip().isdigit() else None
    mandat = _mandat_from_form(organe, fonction, full_name, email, telephone, date_debut, date_fin, fid, db)
    db.add(mandat)
    db.flush()
    log_action(db, user, "creation", "mandat", mandat.id, f"{organe} — {mandat.full_name}")
    db.commit()
    # Redirection interne uniquement
    return _redirect(next if next.startswith("/") and not next.startswith("//") else "/mandats")


@router.post("/mandats/{mandat_id}/delete")
def mandat_delete(mandat_id: int, next: str = Form("/mandats"),
                  user: models.User = Depends(require_member_manager), db: Session = Depends(get_db)):
    mandat = db.get(models.Mandat, mandat_id)
    if not mandat:
        raise HTTPException(status_code=404, detail="Mandat introuvable")
    log_action(db, user, "suppression", "mandat", mandat.id, f"{mandat.organe} — {mandat.full_name}")
    db.delete(mandat)
    db.commit()
    return _redirect(next if next.startswith("/") and not next.startswith("//") else "/mandats")


# ---------- Comptes (administrateur) ----------

@router.get("/users")
def users_list(request: Request, user: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    items = db.query(models.User).order_by(models.User.role, models.User.email).all()
    faitieres = db.query(models.Faitiere).order_by(models.Faitiere.sigle).all()
    return render(request, "users_list.html", user, items=items, faitieres=faitieres)


@router.post("/users")
def user_create(
    email: str = Form(...), full_name: str = Form(...), role: str = Form(...), password: str = Form(...),
    faitiere_id: str = Form(""), origine_id: str = Form(""),
    user: models.User = Depends(require_admin), db: Session = Depends(get_db),
):
    if role not in models.ROLES:
        raise HTTPException(status_code=400, detail="Rôle invalide")
    error = password_policy_error(password)
    if error:
        raise HTTPException(status_code=400, detail=error)
    fid = int(faitiere_id) if faitiere_id.strip().isdigit() else None
    if role == "faitiere" and (fid is None or not db.get(models.Faitiere, fid)):
        raise HTTPException(status_code=400, detail="Un représentant de faîtière doit être rattaché à une faîtière")
    if role != "faitiere":
        fid = None
    oid = int(origine_id) if origine_id.strip().isdigit() else None
    if oid is not None and not db.get(models.Faitiere, oid):
        raise HTTPException(status_code=400, detail="Organisation d'origine inconnue")
    new_user = models.User(
        email=email.strip().lower(), full_name=full_name.strip(), role=role,
        hashed_password=hash_password(password), faitiere_id=fid,
        faitiere_origine_id=oid if role in models.SIGNATAIRE_ROLES else None,
    )
    db.add(new_user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Cette adresse e-mail est déjà utilisée")
    log_action(db, user, "creation", "user", new_user.id, f"{new_user.email} ({role})")
    db.commit()
    return _redirect("/users")


@router.post("/users/{user_id}/toggle")
def user_toggle(user_id: int, user: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    target = db.get(models.User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas désactiver votre propre compte")
    target.is_active = not target.is_active
    log_action(db, user, "activation" if target.is_active else "desactivation", "user", target.id, target.email)
    db.commit()
    return _redirect("/users")


# ---------- Journal d'audit ----------

@router.get("/audit")
def audit_list(request: Request, user: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    items = db.query(models.AuditLog).order_by(models.AuditLog.id.desc()).limit(300).all()
    return render(request, "audit_list.html", user, items=items)


@router.post("/users/{user_id}/password")
def user_reset_password(user_id: int, password: str = Form(...), user: models.User = Depends(require_admin),
                        db: Session = Depends(get_db)):
    """Réinitialisation par l'administrateur (mot de passe oublié) : débloque aussi le compte."""
    target = db.get(models.User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    error = password_policy_error(password)
    if error:
        raise HTTPException(status_code=400, detail=error)
    target.hashed_password = hash_password(password)
    target.failed_login_attempts, target.locked_until = 0, None
    log_action(db, user, "reinitialisation_mdp", "user", target.id, target.email)
    db.commit()
    return _redirect("/users")


@router.post("/users/{user_id}/origine")
def user_set_origin(user_id: int, origine_id: str = Form(""), user: models.User = Depends(require_admin),
                    db: Session = Depends(get_db)):
    """Organisation qui a proposé le DEN ou le secrétaire aux finances (contrôle de la double signature)."""
    target = db.get(models.User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    if target.role not in models.SIGNATAIRE_ROLES:
        raise HTTPException(status_code=400, detail="Seuls le DEN et le secrétaire aux finances ont une organisation d'origine")
    oid = int(origine_id) if origine_id.strip().isdigit() else None
    if oid is not None and not db.get(models.Faitiere, oid):
        raise HTTPException(status_code=400, detail="Organisation inconnue")
    target.faitiere_origine_id = oid
    log_action(db, user, "origine", "user", target.id, f"{target.email} -> {oid}")
    db.commit()
    return _redirect("/users")
