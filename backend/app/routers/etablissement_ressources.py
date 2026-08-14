"""Bibliothèque pédagogique : les établissements partagent des supports (manuels,
fiches de cours) entre eux, modérés par le BEN avant publication."""

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_etab_ressources_web
from ..models import RESSOURCE_CATEGORIES
from .admin_files import ALLOWED_DOCUMENT_EXT, UPLOAD_ROOT, _save_upload

router = APIRouter(tags=["etablissement-ressources"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

RESSOURCES_DIR = UPLOAD_ROOT / "ressources_pedagogiques"


@router.get("/etablissement/ressources")
def etablissement_ressources(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_ressources_web),
):
    etablissement = user.etablissement
    partagees = (
        db.query(models.RessourcePedagogique)
        .filter(models.RessourcePedagogique.is_published.is_(True))
        .order_by(models.RessourcePedagogique.created_at.desc())
        .all()
    )
    mes_depots = (
        db.query(models.RessourcePedagogique)
        .filter(models.RessourcePedagogique.etablissement_id == etablissement.id)
        .order_by(models.RessourcePedagogique.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "etablissement/ressources.html",
        {
            "user": user,
            "etablissement": etablissement,
            "partagees": partagees,
            "mes_depots": mes_depots,
            "categories": RESSOURCE_CATEGORIES,
            "active": "ressources",
            "error": None,
        },
    )


@router.post("/etablissement/ressources/new")
async def etablissement_ressources_create(
    request: Request,
    titre: str = Form(...),
    categorie: str = Form("autre"),
    niveau: str = Form("les_deux"),
    description: str = Form(""),
    file: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_ressources_web),
):
    etablissement = user.etablissement

    if file is None or not file.filename:
        return RedirectResponse(url="/etablissement/ressources", status_code=status.HTTP_303_SEE_OTHER)

    try:
        stored_name, original_name = await _save_upload(file, RESSOURCES_DIR, ALLOWED_DOCUMENT_EXT)
    except ValueError as exc:
        partagees = (
            db.query(models.RessourcePedagogique)
            .filter(models.RessourcePedagogique.is_published.is_(True))
            .order_by(models.RessourcePedagogique.created_at.desc())
            .all()
        )
        mes_depots = (
            db.query(models.RessourcePedagogique)
            .filter(models.RessourcePedagogique.etablissement_id == etablissement.id)
            .order_by(models.RessourcePedagogique.created_at.desc())
            .all()
        )
        return templates.TemplateResponse(
            request,
            "etablissement/ressources.html",
            {
                "user": user,
                "etablissement": etablissement,
                "partagees": partagees,
                "mes_depots": mes_depots,
                "categories": RESSOURCE_CATEGORIES,
                "active": "ressources",
                "error": str(exc),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    ressource = models.RessourcePedagogique(
        titre=titre,
        description=description or None,
        categorie=categorie if categorie in RESSOURCE_CATEGORIES else "autre",
        niveau=niveau if niveau in {"primaire", "secondaire", "les_deux"} else "les_deux",
        file_path=f"ressources_pedagogiques/{stored_name}",
        original_filename=original_name,
        etablissement_id=etablissement.id,
        uploaded_by_id=user.id,
        is_published=False,
    )
    db.add(ressource)
    db.commit()
    return RedirectResponse(url="/etablissement/ressources", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/etablissement/ressources/{ressource_id}/delete")
def etablissement_ressources_delete(
    ressource_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_ressources_web),
):
    ressource = db.get(models.RessourcePedagogique, ressource_id)
    if ressource and ressource.etablissement_id == user.etablissement.id:
        path = UPLOAD_ROOT / ressource.file_path
        db.delete(ressource)
        db.commit()
        if path.exists():
            path.unlink()
    return RedirectResponse(url="/etablissement/ressources", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/etablissement/ressources/{ressource_id}/file")
def etablissement_ressources_file(
    ressource_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_ressources_web),
):
    ressource = db.get(models.RessourcePedagogique, ressource_id)
    if not ressource:
        raise HTTPException(status_code=404, detail="Ressource introuvable")
    if not ressource.is_published and ressource.etablissement_id != user.etablissement.id:
        raise HTTPException(status_code=404, detail="Ressource introuvable")
    path = UPLOAD_ROOT / ressource.file_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    media_type = mimetypes.guess_type(ressource.file_path)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=ressource.original_filename)
