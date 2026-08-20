from pathlib import Path

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import audit, models, storage
from ..database import get_db
from ..deps import require_site_content_access_web
from ..site_content_fields import SITE_CONTENT_FIELDS
from .admin_files import ALLOWED_PHOTO_EXT

router = APIRouter(prefix="/admin/site-content", tags=["admin-site-content"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

SITE_CONTENT_IMAGES_DIR = "site_content"


def _grouped_fields(values: dict[str, str]) -> list[tuple[str, list[dict]]]:
    groups: dict[str, list[dict]] = {}
    for key, meta in SITE_CONTENT_FIELDS.items():
        value = values.get(key, "")
        groups.setdefault(meta["group"], []).append(
            {
                "key": key,
                "label": meta["label"],
                "type": meta["type"],
                "default": meta["default"],
                "value": value,
                "image_url": f"/api/site-content/{key}/image" if meta["type"] == "image" and value else None,
            }
        )
    return list(groups.items())


@router.get("")
def site_content_form(
    request: Request,
    saved: bool = False,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_site_content_access_web),
):
    rows = db.query(models.SiteContent).all()
    values = {r.key: r.value or "" for r in rows}
    return templates.TemplateResponse(
        request,
        "admin/site_content_form.html",
        {"admin": user, "active": "site_content", "groups": _grouped_fields(values), "saved": saved},
    )


@router.post("")
async def site_content_save(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_site_content_access_web),
):
    form = await request.form()
    for key, meta in SITE_CONTENT_FIELDS.items():
        row = db.get(models.SiteContent, key)
        if not row:
            row = models.SiteContent(key=key)
            db.add(row)

        if meta["type"] == "image":
            if form.get("remove_" + key):
                storage.delete_stored_file(db, row.value)
                row.value = None
            else:
                upload = form.get(key)
                if upload is not None and getattr(upload, "filename", None):
                    try:
                        stored_name, _ = await storage.save_upload(db, upload, SITE_CONTENT_IMAGES_DIR, ALLOWED_PHOTO_EXT)
                    except ValueError:
                        stored_name = None
                    if stored_name:
                        storage.delete_stored_file(db, row.value)
                        row.value = f"site_content/{stored_name}"
        else:
            value = str(form.get(key, "")).strip()
            row.value = value or None

        row.updated_by_id = user.id
    audit.log(db, user, "update", "Contenu du site", None, "A modifié le contenu du site vitrine")
    db.commit()
    return RedirectResponse(url="/admin/site-content?saved=true", status_code=status.HTTP_303_SEE_OTHER)
