from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import audit, models
from ..database import get_db
from ..deps import require_admin_web
from ..postes import DEFAULT_MODULES_BY_POSTE, MODULES, POSTES
from ..security import hash_password, password_policy_error
from .admin_files import UPLOAD_ROOT

router = APIRouter(prefix="/admin/users", tags=["admin-users"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def users_list(
    request: Request,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin_web),
):
    items = db.query(models.User).order_by(models.User.full_name).all()
    return templates.TemplateResponse(
        request,
        "admin/users_list.html",
        {"admin": admin, "items": items, "active": "users", "modules": MODULES},
    )


@router.get("/new")
def users_new_form(
    request: Request,
    admin: models.User = Depends(require_admin_web),
):
    return templates.TemplateResponse(
        request,
        "admin/user_form.html",
        {
            "admin": admin,
            "item": None,
            "postes": POSTES,
            "modules": MODULES,
            "defaults_by_poste": DEFAULT_MODULES_BY_POSTE,
            "active": "users",
            "error": None,
        },
    )


@router.post("/new")
def users_create(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    access_level: str = Form("bureau"),
    poste: str = Form(""),
    is_adjoint: bool = Form(False),
    modules: list[str] = Form([]),
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin_web),
):
    existing = db.query(models.User).filter(models.User.email == email).first()
    password_error = password_policy_error(password)
    if existing or password_error:
        return templates.TemplateResponse(
            request,
            "admin/user_form.html",
            {
                "admin": admin,
                "item": None,
                "postes": POSTES,
                "modules": MODULES,
                "defaults_by_poste": DEFAULT_MODULES_BY_POSTE,
                "active": "users",
                "error": "Un compte existe déjà avec cet e-mail." if existing else password_error,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    valid_modules = [m for m in modules if m in MODULES]
    user = models.User(
        full_name=full_name,
        email=email,
        hashed_password=hash_password(password),
        access_level=access_level if access_level in {"admin", "bureau", "observateur"} else "bureau",
        poste=poste or None,
        is_adjoint=is_adjoint,
        allowed_modules=",".join(valid_modules),
    )
    db.add(user)
    db.flush()
    audit.log(db, admin, "create", "Compte utilisateur", user.id, f"A créé le compte de {user.full_name} ({user.email})")
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{user_id}/edit")
def users_edit_form(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin_web),
):
    item = db.get(models.User, user_id)
    if not item:
        return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request,
        "admin/user_form.html",
        {
            "admin": admin,
            "item": item,
            "postes": POSTES,
            "modules": MODULES,
            "defaults_by_poste": DEFAULT_MODULES_BY_POSTE,
            "active": "users",
            "error": None,
        },
    )


@router.post("/{user_id}/edit")
def users_update(
    user_id: int,
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(""),
    access_level: str = Form("bureau"),
    poste: str = Form(""),
    is_adjoint: bool = Form(False),
    modules: list[str] = Form([]),
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin_web),
):
    user = db.get(models.User, user_id)
    if user:
        duplicate = (
            db.query(models.User)
            .filter(models.User.email == email, models.User.id != user_id)
            .first()
        )
        password_error = password_policy_error(password) if password else None
        if duplicate or password_error:
            return templates.TemplateResponse(
                request,
                "admin/user_form.html",
                {
                    "admin": admin,
                    "item": user,
                    "postes": POSTES,
                    "modules": MODULES,
                    "defaults_by_poste": DEFAULT_MODULES_BY_POSTE,
                    "active": "users",
                    "error": "Un autre compte utilise déjà cet e-mail." if duplicate else password_error,
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        valid_modules = [m for m in modules if m in MODULES]
        user.full_name = full_name
        user.email = email
        user.access_level = access_level if access_level in {"admin", "bureau", "observateur"} else "bureau"
        user.poste = poste or None
        user.is_adjoint = is_adjoint
        user.allowed_modules = ",".join(valid_modules)
        if password:
            user.hashed_password = hash_password(password)
        audit.log(db, admin, "update", "Compte utilisateur", user.id, f"A modifié le compte de {user.full_name} ({user.email})")
        db.commit()
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{user_id}/deverrouiller")
def users_unlock(
    user_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin_web),
):
    user = db.get(models.User, user_id)
    if user:
        user.failed_login_attempts = 0
        user.locked_until = None
        audit.log(db, admin, "update", "Compte utilisateur", user.id, f"A déverrouillé le compte de {user.full_name}")
        db.commit()
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{user_id}/delete")
def users_delete(
    user_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin_web),
):
    if user_id == admin.id:
        return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)
    user = db.get(models.User, user_id)
    if user:
        # Les CarteMembre du compte sont supprimées en cascade côté base
        # (ondelete="CASCADE"), mais leurs photos sur disque ne le sont jamais
        # automatiquement — on les collecte avant le commit pour ne pas laisser
        # de fichiers orphelins.
        photo_paths = [
            UPLOAD_ROOT / c.photo_path
            for c in db.query(models.CarteMembre).filter(models.CarteMembre.user_id == user_id).all()
            if c.photo_path
        ]
        audit.log(db, admin, "delete", "Compte utilisateur", user.id, f"A révoqué le compte de {user.full_name} ({user.email})")
        db.delete(user)
        db.commit()
        for path in photo_paths:
            if path.exists():
                path.unlink()
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)
