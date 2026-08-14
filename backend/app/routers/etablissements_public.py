"""Ressources publiques liées aux établissements affiliés (ex. logo, utilisé sur
les cartes scolaires de leurs élèves et dans leur espace personnel)."""

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..badge import generate_membership_badge_svg
from ..database import get_db
from .admin_files import UPLOAD_ROOT

router = APIRouter(prefix="/api/etablissements", tags=["etablissements"])

LOGO_PATH = Path(__file__).resolve().parent.parent / "static" / "img" / "logo.jpg"


@router.get("", response_model=list[schemas.EtablissementPublicOut])
def list_etablissements(db: Session = Depends(get_db)):
    """Liste publique des établissements affiliés, pour la page vitrine dédiée —
    triée par région (bureau local) puis par nom."""
    items = (
        db.query(models.Etablissement)
        .order_by(models.Etablissement.bureau_local, models.Etablissement.nom)
        .all()
    )
    return items


@router.get("/stats", response_model=schemas.EtablissementsStatsOut)
def etablissements_stats(db: Session = Depends(get_db)):
    """Chiffres clés publics pour la page d'accueil de la vitrine."""
    ecoles = db.query(models.Etablissement).count()
    regions = (
        db.query(models.Etablissement.bureau_local)
        .filter(models.Etablissement.bureau_local.isnot(None))
        .distinct()
        .count()
    )
    enseignants = db.query(models.Enseignant).count()

    derniere_annee = db.query(func.max(models.Effectif.annee_scolaire)).scalar()
    eleves = 0
    if derniere_annee:
        total_garcons, total_filles = (
            db.query(
                func.coalesce(func.sum(models.Effectif.nombre_garcons), 0),
                func.coalesce(func.sum(models.Effectif.nombre_filles), 0),
            )
            .filter(models.Effectif.annee_scolaire == derniere_annee)
            .one()
        )
        eleves = total_garcons + total_filles

    return schemas.EtablissementsStatsOut(
        ecoles=ecoles, regions=regions, enseignants=enseignants, eleves=eleves
    )


@router.get("/{etablissement_id}/logo")
def etablissement_logo(etablissement_id: int, db: Session = Depends(get_db)):
    etablissement = db.get(models.Etablissement, etablissement_id)
    if not etablissement or not etablissement.logo_path:
        return FileResponse(LOGO_PATH, media_type="image/jpeg")
    path = UPLOAD_ROOT / etablissement.logo_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="Logo introuvable")
    media_type = mimetypes.guess_type(etablissement.logo_path)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)


@router.get("/{etablissement_id}/badge.svg")
def etablissement_badge(etablissement_id: int, db: Session = Depends(get_db)):
    """Badge d'affiliation LECIM à intégrer sur le site propre de l'établissement."""
    etablissement = db.get(models.Etablissement, etablissement_id)
    if not etablissement:
        raise HTTPException(status_code=404, detail="Établissement introuvable")
    svg = generate_membership_badge_svg(etablissement)
    return Response(content=svg, media_type="image/svg+xml")
