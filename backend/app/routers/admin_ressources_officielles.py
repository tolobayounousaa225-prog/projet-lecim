from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models, storage
from ..database import get_db
from ..deps import require_publications_access_web
from ..models import RESSOURCE_OFFICIELLE_LANGUES, RESSOURCE_OFFICIELLE_SECTIONS
from .admin_files import ALLOWED_DOCUMENT_EXT, ALLOWED_PHOTO_EXT

router = APIRouter(prefix="/admin/ressources-officielles", tags=["admin-ressources-officielles"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

RESSOURCES_OFFICIELLES_DIR = "ressources_officielles"


@router.get("")
def ressources_officielles_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    items = (
        db.query(models.RessourceOfficielle)
        .order_by(models.RessourceOfficielle.section, models.RessourceOfficielle.ordre)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/ressources_officielles_list.html",
        {
            "admin": user,
            "items": items,
            "sections": RESSOURCE_OFFICIELLE_SECTIONS,
            "active": "ressources_officielles",
        },
    )


@router.get("/new")
def ressources_officielles_new_form(
    request: Request,
    user: models.User = Depends(require_publications_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/ressource_officielle_form.html",
        {
            "admin": user,
            "sections": RESSOURCE_OFFICIELLE_SECTIONS,
            "langues": RESSOURCE_OFFICIELLE_LANGUES,
            "active": "ressources_officielles",
            "error": None,
        },
    )


@router.post("/new")
async def ressources_officielles_create(
    request: Request,
    titre: str = Form(...),
    section: str = Form(...),
    langue: str = Form(""),
    description: str = Form(""),
    ordre: int = Form(0),
    is_published: bool = Form(False),
    photo: UploadFile | None = None,
    file: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    error_ctx = {
        "admin": user,
        "sections": RESSOURCE_OFFICIELLE_SECTIONS,
        "langues": RESSOURCE_OFFICIELLE_LANGUES,
        "active": "ressources_officielles",
    }
    try:
        if photo is None or not photo.filename:
            raise ValueError("Une photo est obligatoire")
        photo_stored_name, _ = await storage.save_upload(db, photo, RESSOURCES_OFFICIELLES_DIR, ALLOWED_PHOTO_EXT)
    except ValueError as exc:
        return templates.TemplateResponse(
            request, "admin/ressource_officielle_form.html",
            {**error_ctx, "error": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST,
        )

    file_stored_name = None
    file_original_name = None
    if file is not None and file.filename:
        try:
            file_stored_name, file_original_name = await storage.save_upload(
                db, file, RESSOURCES_OFFICIELLES_DIR, ALLOWED_DOCUMENT_EXT
            )
        except ValueError as exc:
            return templates.TemplateResponse(
                request, "admin/ressource_officielle_form.html",
                {**error_ctx, "error": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST,
            )

    ressource = models.RessourceOfficielle(
        titre=titre,
        section=section if section in RESSOURCE_OFFICIELLE_SECTIONS else "manuel_scolaire",
        langue=langue if langue in RESSOURCE_OFFICIELLE_LANGUES else None,
        description=description or None,
        photo_path=f"ressources_officielles/{photo_stored_name}",
        file_path=f"ressources_officielles/{file_stored_name}" if file_stored_name else None,
        original_filename=file_original_name,
        ordre=ordre,
        is_published=is_published,
        uploaded_by_id=user.id,
    )
    db.add(ressource)
    db.commit()
    return RedirectResponse(url="/admin/ressources-officielles", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{ressource_id}/delete")
def ressources_officielles_delete(
    ressource_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    ressource = db.get(models.RessourceOfficielle, ressource_id)
    if ressource:
        storage.delete_stored_file(db, ressource.photo_path)
        storage.delete_stored_file(db, ressource.file_path)
        db.delete(ressource)
        db.commit()
    return RedirectResponse(url="/admin/ressources-officielles", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{ressource_id}/toggle")
def ressources_officielles_toggle(
    ressource_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    ressource = db.get(models.RessourceOfficielle, ressource_id)
    if ressource:
        ressource.is_published = not ressource.is_published
        db.commit()
    return RedirectResponse(url="/admin/ressources-officielles", status_code=status.HTTP_303_SEE_OTHER)
