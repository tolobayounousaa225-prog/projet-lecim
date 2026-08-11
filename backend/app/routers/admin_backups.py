from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import audit, backup, models
from ..database import get_db
from ..deps import require_admin_web

router = APIRouter(prefix="/admin/backups", tags=["admin-backups"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def backups_list(
    request: Request,
    error: str | None = None,
    admin: models.User = Depends(require_admin_web),
):
    return templates.TemplateResponse(
        request,
        "admin/backups_list.html",
        {"admin": admin, "active": "backups", "items": backup.list_backups(), "error": error},
    )


@router.post("/new")
def backups_create(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin_web),
):
    try:
        destination = backup.create_backup()
        audit.log(db, admin, "create", "Sauvegarde", None, f"A déclenché une sauvegarde manuelle ({destination.name})")
        db.commit()
    except Exception as exc:
        return RedirectResponse(url=f"/admin/backups?error={quote(str(exc))}", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/admin/backups", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{filename}/download")
def backups_download(
    filename: str,
    admin: models.User = Depends(require_admin_web),
):
    if "/" in filename or "\\" in filename or not filename.startswith("lecim-"):
        return RedirectResponse(url="/admin/backups", status_code=status.HTTP_303_SEE_OTHER)
    path = backup.BACKUP_DIR / filename
    if not path.exists():
        return RedirectResponse(url="/admin/backups", status_code=status.HTTP_303_SEE_OTHER)
    return FileResponse(path, filename=filename)
