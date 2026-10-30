"""Vérification publique d'authenticité d'une carte de membre (page ouverte au scan du QR code).

Aucune authentification n'est requise pour la vérification de base — c'est le but :
n'importe qui (agent de sécurité, partenaire, etc.) doit pouvoir scanner une carte
physique et vérifier son authenticité (nom, photo, validité). Les informations
confidentielles du titulaire (CNI, téléphone, contact d'urgence, date de naissance,
adresse) ne sont montrées en plus que si la personne qui scanne est, dans son propre
navigateur, connectée à l'espace admin LECIM avec l'accès au module cartes_gestion —
jamais au grand public.
"""

import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models, storage
from ..database import get_db
from ..deps import get_optional_cartes_gestion_user
from ..rate_limit import rate_limiter

router = APIRouter(prefix="/verify", tags=["verify"], dependencies=[Depends(rate_limiter("verify-carte", 30, 60))])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

VALID_STATUSES = {"validee", "imprimee", "disponible"}


def _check(carte: models.CarteMembre | None) -> str:
    if not carte or carte.status not in VALID_STATUSES:
        return "introuvable"
    if carte.date_validite and carte.date_validite < datetime.date.today():
        return "expiree"
    return "authentique"


@router.get("/{numero_carte}")
def verify_card(
    numero_carte: str,
    request: Request,
    db: Session = Depends(get_db),
    staff_viewer: models.User | None = Depends(get_optional_cartes_gestion_user),
):
    carte = (
        db.query(models.CarteMembre)
        .filter(models.CarteMembre.numero_carte == numero_carte)
        .first()
    )
    result = _check(carte)
    return templates.TemplateResponse(
        request,
        "verify.html",
        {
            "carte": carte,
            "result": result,
            "numero_carte": numero_carte,
            "show_confidential": staff_viewer is not None,
        },
    )


@router.get("/{numero_carte}/photo")
def verify_card_photo(numero_carte: str, db: Session = Depends(get_db)):
    carte = (
        db.query(models.CarteMembre)
        .filter(models.CarteMembre.numero_carte == numero_carte)
        .first()
    )
    if _check(carte) != "introuvable" and carte.photo_path:
        stored = storage.get_stored_file(db, carte.photo_path)
        if stored:
            return Response(content=stored.data, media_type=stored.content_type)
    return FileResponse(
        Path(__file__).resolve().parent.parent / "static" / "img" / "logo.jpg",
        media_type="image/jpeg",
    )
