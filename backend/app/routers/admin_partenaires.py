from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_partenaires_access_web
from ..models import PARTENAIRE_STATUTS, PARTENAIRE_TYPES
from .admin_files import ALLOWED_PHOTO_EXT, UPLOAD_ROOT, _save_upload

router = APIRouter(prefix="/admin/partenaires", tags=["admin-partenaires"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

PARTENAIRE_LOGOS_DIR = UPLOAD_ROOT / "partenaires_logos"


@router.get("")
def partenaires_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_partenaires_access_web),
):
    # Les demandes liées à un projet précis se gèrent depuis la fiche de ce
    # projet (/admin/projets/{id}/edit), pas ici — cette liste ne montre que
    # les partenariats généraux, non rattachés à un projet publié.
    items = (
        db.query(models.Partenaire)
        .filter(models.Partenaire.projet_id.is_(None))
        .order_by(models.Partenaire.nom)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/partenaires_list.html",
        {
            "admin": user,
            "items": items,
            "types": PARTENAIRE_TYPES,
            "statuts": PARTENAIRE_STATUTS,
            "active": "partenaires",
        },
    )


@router.get("/new")
def partenaires_new_form(
    request: Request,
    user: models.User = Depends(require_partenaires_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/partenaire_form.html",
        {"admin": user, "item": None, "types": PARTENAIRE_TYPES, "statuts": PARTENAIRE_STATUTS, "active": "partenaires"},
    )


@router.post("/new")
async def partenaires_create(
    nom: str = Form(...),
    type: str = Form("autre"),
    pays: str = Form(""),
    contact_nom: str = Form(""),
    contact_email: str = Form(""),
    contact_telephone: str = Form(""),
    statut: str = Form("en_discussion"),
    notes: str = Form(""),
    logo: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_partenaires_access_web),
):
    logo_path = None
    if logo is not None and logo.filename:
        try:
            stored_name, _ = await _save_upload(logo, PARTENAIRE_LOGOS_DIR, ALLOWED_PHOTO_EXT)
            logo_path = f"partenaires_logos/{stored_name}"
        except ValueError:
            pass

    partenaire = models.Partenaire(
        nom=nom,
        type=type if type in PARTENAIRE_TYPES else "autre",
        pays=pays or None,
        logo_path=logo_path,
        contact_nom=contact_nom or None,
        contact_email=contact_email or None,
        contact_telephone=contact_telephone or None,
        statut=statut if statut in PARTENAIRE_STATUTS else "en_discussion",
        notes=notes or None,
        created_by_id=user.id,
    )
    db.add(partenaire)
    db.commit()
    return RedirectResponse(url="/admin/partenaires", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{partenaire_id}/edit")
def partenaires_edit_form(
    partenaire_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_partenaires_access_web),
):
    item = db.get(models.Partenaire, partenaire_id)
    return templates.TemplateResponse(
        request,
        "admin/partenaire_form.html",
        {"admin": user, "item": item, "types": PARTENAIRE_TYPES, "statuts": PARTENAIRE_STATUTS, "active": "partenaires"},
    )


@router.post("/{partenaire_id}/edit")
async def partenaires_update(
    partenaire_id: int,
    nom: str = Form(...),
    type: str = Form("autre"),
    pays: str = Form(""),
    contact_nom: str = Form(""),
    contact_email: str = Form(""),
    contact_telephone: str = Form(""),
    statut: str = Form("en_discussion"),
    notes: str = Form(""),
    logo: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_partenaires_access_web),
):
    partenaire = db.get(models.Partenaire, partenaire_id)
    if partenaire:
        if logo is not None and logo.filename:
            try:
                stored_name, _ = await _save_upload(logo, PARTENAIRE_LOGOS_DIR, ALLOWED_PHOTO_EXT)
                old_path = UPLOAD_ROOT / partenaire.logo_path if partenaire.logo_path else None
                partenaire.logo_path = f"partenaires_logos/{stored_name}"
                if old_path and old_path.exists():
                    old_path.unlink()
            except ValueError:
                pass

        partenaire.nom = nom
        partenaire.type = type if type in PARTENAIRE_TYPES else "autre"
        partenaire.pays = pays or None
        partenaire.contact_nom = contact_nom or None
        partenaire.contact_email = contact_email or None
        partenaire.contact_telephone = contact_telephone or None
        partenaire.statut = statut if statut in PARTENAIRE_STATUTS else "en_discussion"
        partenaire.notes = notes or None
        db.commit()
    return RedirectResponse(url="/admin/partenaires", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{partenaire_id}/delete")
def partenaires_delete(
    partenaire_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_partenaires_access_web),
):
    partenaire = db.get(models.Partenaire, partenaire_id)
    if partenaire:
        db.delete(partenaire)
        db.commit()
    return RedirectResponse(url="/admin/partenaires", status_code=status.HTTP_303_SEE_OTHER)
