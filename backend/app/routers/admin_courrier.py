import datetime
import csv
import io
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import audit, models, storage
from ..database import get_db
from ..deps import require_courrier_access_web
from ..models import COURRIER_TYPES
from .admin_files import ALLOWED_DOCUMENT_EXT, ALLOWED_PHOTO_EXT

router = APIRouter(prefix="/admin/courrier", tags=["admin-courrier"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

COURRIER_DIR = "courrier"
ALLOWED_COURRIER_EXT = ALLOWED_DOCUMENT_EXT | ALLOWED_PHOTO_EXT
COURRIER_PREFIXES = {"arrivee": "ARR", "depart": "DEP"}


def _apply_filters(query, type: str | None, q: str | None):
    if type in COURRIER_TYPES:
        query = query.filter(models.Courrier.type == type)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(models.Courrier.correspondant.ilike(like), models.Courrier.objet.ilike(like)))
    return query


def _suggest_numero(db: Session, type: str) -> str:
    """Numéro de référence suggéré (modifiable) : préfixe du type + année en
    cours + rang, pour limiter les doublons de saisie manuelle sans imposer
    une numérotation stricte (certaines organisations ont leur propre
    convention héritée du registre papier)."""
    year = datetime.date.today().year
    count = (
        db.query(models.Courrier)
        .filter(models.Courrier.type == type, models.Courrier.date_courrier >= datetime.date(year, 1, 1))
        .count()
    )
    return f"{COURRIER_PREFIXES.get(type, type.upper())}-{year}-{count + 1:03d}"


@router.get("")
def courrier_list(
    request: Request,
    type: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_courrier_access_web),
):
    query = _apply_filters(db.query(models.Courrier), type, q)
    items = query.order_by(models.Courrier.date_courrier.desc(), models.Courrier.id.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin/courrier_list.html",
        {"admin": user, "items": items, "types": COURRIER_TYPES, "filtre_type": type, "q": q or "", "active": "courrier"},
    )


@router.get("/export.csv")
def courrier_export_csv(
    type: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_courrier_access_web),
):
    query = _apply_filters(db.query(models.Courrier), type, q)
    items = query.order_by(models.Courrier.date_courrier.desc(), models.Courrier.id.desc()).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Type", "Numéro", "Date", "Correspondant", "Objet", "Observation"])
    for item in items:
        writer.writerow([
            item.type_label, item.numero, item.date_courrier.strftime("%d/%m/%Y"),
            item.correspondant, item.objet, item.observation or "",
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="registre-courrier.csv"'},
    )


@router.get("/new")
def courrier_new_form(
    request: Request,
    type: str = "arrivee",
    db: Session = Depends(get_db),
    user: models.User = Depends(require_courrier_access_web),
):
    suggestions = {key: _suggest_numero(db, key) for key in COURRIER_TYPES}
    return templates.TemplateResponse(
        request,
        "admin/courrier_form.html",
        {
            "admin": user, "item": None, "types": COURRIER_TYPES, "active": "courrier", "error": None,
            "suggestions": suggestions, "default_type": type if type in COURRIER_TYPES else "arrivee",
        },
    )


@router.post("/new")
async def courrier_create(
    request: Request,
    type: str = Form(...),
    numero: str = Form(...),
    date_courrier: str = Form(...),
    correspondant: str = Form(...),
    objet: str = Form(...),
    observation: str = Form(""),
    file: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_courrier_access_web),
):
    error_ctx = {"admin": user, "item": None, "types": COURRIER_TYPES, "active": "courrier"}
    if type not in COURRIER_TYPES:
        return templates.TemplateResponse(
            request, "admin/courrier_form.html",
            {**error_ctx, "error": "Type de courrier invalide."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    file_path = None
    original_filename = None
    if file is not None and file.filename:
        try:
            stored_name, original_filename = await storage.save_upload(db, file, COURRIER_DIR, ALLOWED_COURRIER_EXT)
            file_path = f"{COURRIER_DIR}/{stored_name}"
        except ValueError as exc:
            return templates.TemplateResponse(
                request, "admin/courrier_form.html",
                {**error_ctx, "error": str(exc)},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    try:
        parsed_date = datetime.date.fromisoformat(date_courrier)
    except ValueError:
        return templates.TemplateResponse(
            request, "admin/courrier_form.html",
            {**error_ctx, "error": "Date invalide."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    courrier = models.Courrier(
        type=type, numero=numero, date_courrier=parsed_date, correspondant=correspondant,
        objet=objet, observation=observation or None, file_path=file_path,
        original_filename=original_filename, created_by_id=user.id,
    )
    db.add(courrier)
    db.flush()
    audit.log(db, user, "create", "Courrier", courrier.id, f"A enregistré le courrier {numero} ({correspondant})")
    db.commit()
    return RedirectResponse(url="/admin/courrier", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{courrier_id}/edit")
def courrier_edit_form(
    courrier_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_courrier_access_web),
):
    item = db.get(models.Courrier, courrier_id)
    if not item:
        return RedirectResponse(url="/admin/courrier", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request,
        "admin/courrier_form.html",
        {"admin": user, "item": item, "types": COURRIER_TYPES, "active": "courrier", "error": None},
    )


@router.post("/{courrier_id}/edit")
async def courrier_update(
    courrier_id: int,
    request: Request,
    type: str = Form(...),
    numero: str = Form(...),
    date_courrier: str = Form(...),
    correspondant: str = Form(...),
    objet: str = Form(...),
    observation: str = Form(""),
    file: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_courrier_access_web),
):
    item = db.get(models.Courrier, courrier_id)
    if not item:
        return RedirectResponse(url="/admin/courrier", status_code=status.HTTP_303_SEE_OTHER)

    error_ctx = {"admin": user, "item": item, "types": COURRIER_TYPES, "active": "courrier"}
    if type not in COURRIER_TYPES:
        return templates.TemplateResponse(
            request, "admin/courrier_form.html",
            {**error_ctx, "error": "Type de courrier invalide."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        parsed_date = datetime.date.fromisoformat(date_courrier)
    except ValueError:
        return templates.TemplateResponse(
            request, "admin/courrier_form.html",
            {**error_ctx, "error": "Date invalide."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if file is not None and file.filename:
        try:
            stored_name, original_filename = await storage.save_upload(db, file, COURRIER_DIR, ALLOWED_COURRIER_EXT)
            storage.delete_stored_file(db, item.file_path)
            item.file_path = f"{COURRIER_DIR}/{stored_name}"
            item.original_filename = original_filename
        except ValueError as exc:
            return templates.TemplateResponse(
                request, "admin/courrier_form.html",
                {**error_ctx, "error": str(exc)},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    item.type = type
    item.numero = numero
    item.date_courrier = parsed_date
    item.correspondant = correspondant
    item.objet = objet
    item.observation = observation or None
    audit.log(db, user, "update", "Courrier", item.id, f"A modifié le courrier {numero} ({correspondant})")
    db.commit()
    return RedirectResponse(url="/admin/courrier", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{courrier_id}/delete")
def courrier_delete(
    courrier_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_courrier_access_web),
):
    item = db.get(models.Courrier, courrier_id)
    if item:
        storage.delete_stored_file(db, item.file_path)
        audit.log(db, user, "delete", "Courrier", item.id, f"A supprimé le courrier {item.numero} ({item.correspondant})")
        db.delete(item)
        db.commit()
    return RedirectResponse(url="/admin/courrier", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{courrier_id}/file")
def courrier_file(
    courrier_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_courrier_access_web),
):
    item = db.get(models.Courrier, courrier_id)
    if not item or not item.file_path:
        return RedirectResponse(url="/admin/courrier", status_code=status.HTTP_303_SEE_OTHER)
    stored = storage.get_stored_file(db, item.file_path)
    if not stored:
        return RedirectResponse(url="/admin/courrier", status_code=status.HTTP_303_SEE_OTHER)
    return Response(
        content=stored.data,
        media_type=stored.content_type,
        headers={"Content-Disposition": f'attachment; filename="{item.original_filename}"'},
    )
