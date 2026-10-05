from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import backup, models
from ..database import get_db
from ..deps import require_admin_web

router = APIRouter(prefix="/admin/systeme", tags=["admin-systeme"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def systeme_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin_web),
):
    backups = backup.list_backups()
    derniere_sauvegarde = backups[0] if backups else None

    fichiers_count, fichiers_taille_octets = db.query(
        func.count(models.StoredFile.id), func.coalesce(func.sum(func.length(models.StoredFile.data)), 0)
    ).first()

    compteurs = {
        "Comptes utilisateurs": db.query(models.User).count(),
        "Établissements affiliés": db.query(models.Etablissement).count(),
        "Membres du répertoire": db.query(models.Membre).count(),
        "Réunions enregistrées": db.query(models.Reunion).count(),
    }

    return templates.TemplateResponse(
        request,
        "admin/systeme_dashboard.html",
        {
            "admin": admin,
            "active": "systeme",
            "derniere_sauvegarde": derniere_sauvegarde,
            "nb_sauvegardes": len(backups),
            "fichiers_count": fichiers_count,
            "fichiers_taille_mo": round(fichiers_taille_octets / (1024 * 1024), 1),
            "compteurs": compteurs,
        },
    )
