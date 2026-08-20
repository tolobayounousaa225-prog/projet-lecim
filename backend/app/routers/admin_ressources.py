"""Modération des ressources pédagogiques déposées par les établissements —
le BEN valide (ou refuse) chaque dépôt avant qu'il ne devienne visible aux autres
écoles membres."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import audit, models, storage
from ..database import get_db
from ..deps import require_publications_access_web
from ..models import RESSOURCE_CATEGORIES

router = APIRouter(prefix="/admin/ressources-pedagogiques", tags=["admin-ressources"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def ressources_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    items = (
        db.query(models.RessourcePedagogique)
        .order_by(models.RessourcePedagogique.is_published, models.RessourcePedagogique.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/ressources_list.html",
        {"admin": user, "items": items, "categories": RESSOURCE_CATEGORIES, "active": "ressources"},
    )


@router.post("/{ressource_id}/publish")
def ressource_toggle_publish(
    ressource_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    ressource = db.get(models.RessourcePedagogique, ressource_id)
    if ressource:
        ressource.is_published = not ressource.is_published
        if ressource.is_published:
            ressource.moderated_by_id = user.id
        audit.log(
            db, user, "update", "Ressource pédagogique", ressource.id,
            f"A {'publié' if ressource.is_published else 'dépublié'} la ressource « {ressource.titre} »",
        )
        db.commit()
    return RedirectResponse(url="/admin/ressources-pedagogiques", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{ressource_id}/delete")
def ressource_delete(
    ressource_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    ressource = db.get(models.RessourcePedagogique, ressource_id)
    if ressource:
        storage.delete_stored_file(db, ressource.file_path)
        audit.log(db, user, "delete", "Ressource pédagogique", ressource.id, f"A supprimé la ressource « {ressource.titre} »")
        db.delete(ressource)
        db.commit()
    return RedirectResponse(url="/admin/ressources-pedagogiques", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{ressource_id}/file")
def ressource_file(
    ressource_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_publications_access_web),
):
    ressource = db.get(models.RessourcePedagogique, ressource_id)
    if not ressource:
        raise HTTPException(status_code=404, detail="Ressource introuvable")
    stored = storage.get_stored_file(db, ressource.file_path)
    if not stored:
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    return Response(
        content=stored.data,
        media_type=stored.content_type,
        headers={"Content-Disposition": f'attachment; filename="{ressource.original_filename}"'},
    )
