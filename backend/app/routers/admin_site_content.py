from pathlib import Path

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import audit, models
from ..database import get_db
from ..deps import require_site_content_access_web
from ..site_content_fields import SITE_CONTENT_FIELDS

router = APIRouter(prefix="/admin/site-content", tags=["admin-site-content"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def _grouped_fields(values: dict[str, str]) -> list[tuple[str, list[dict]]]:
    groups: dict[str, list[dict]] = {}
    for key, meta in SITE_CONTENT_FIELDS.items():
        groups.setdefault(meta["group"], []).append(
            {
                "key": key,
                "label": meta["label"],
                "type": meta["type"],
                "default": meta["default"],
                "value": values.get(key, ""),
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
    for key in SITE_CONTENT_FIELDS:
        value = str(form.get(key, "")).strip()
        row = db.get(models.SiteContent, key)
        if not row:
            row = models.SiteContent(key=key)
            db.add(row)
        row.value = value or None
        row.updated_by_id = user.id
    audit.log(db, user, "update", "Contenu du site", None, "A modifié le contenu du site vitrine")
    db.commit()
    return RedirectResponse(url="/admin/site-content?saved=true", status_code=status.HTTP_303_SEE_OTHER)
