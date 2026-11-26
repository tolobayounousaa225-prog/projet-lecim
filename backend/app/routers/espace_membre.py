"""Espace Membre public : un titulaire de carte consulte le statut de sa propre
carte et les ressources reservees aux membres, en se verifiant par son numero de
carte ET sa date de naissance (deux facteurs qu'il est seul a connaitre ensemble,
tous deux deja imprimes sur sa carte) — jamais de compte/mot de passe separe.
Rate-limite comme les autres verifications publiques du site (QR, diplomes)."""

import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..rate_limit import rate_limiter
from ..security_utils import safe_content_disposition
from .. import storage

router = APIRouter(prefix="/api/espace-membre", tags=["espace-membre"], dependencies=[Depends(rate_limiter("espace-membre", 15, 60))])


def _find_carte(db: Session, numero_carte: str, date_naissance: str) -> models.CarteMembre | None:
    numero = (numero_carte or "").strip()
    if not numero:
        return None
    try:
        parsed_naissance = datetime.datetime.strptime(date_naissance.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return None
    return (
        db.query(models.CarteMembre)
        .filter(
            models.CarteMembre.numero_carte == numero,
            models.CarteMembre.date_naissance == parsed_naissance,
        )
        .first()
    )


@router.get("/ma-carte")
def ma_carte(numero_carte: str, date_naissance: str, db: Session = Depends(get_db)):
    carte = _find_carte(db, numero_carte, date_naissance)
    if not carte:
        return {"found": False}

    today = datetime.date.today()
    expiree = bool(carte.date_validite and carte.date_validite < today)
    delegation_nom = carte.user.delegation.nom if carte.user and carte.user.delegation else None

    return {
        "found": True,
        "nom_complet": carte.full_name_snapshot,
        "fonction": carte.user.poste_label if carte.user else None,
        "numero_carte": carte.numero_carte,
        "status": carte.status,
        "expiree": expiree,
        "date_validite": carte.date_validite.isoformat() if carte.date_validite else None,
        "delegation": delegation_nom,
    }


@router.get("/ressources")
def ressources(numero_carte: str, date_naissance: str, db: Session = Depends(get_db)):
    carte = _find_carte(db, numero_carte, date_naissance)
    if not carte or carte.status not in {"validee", "imprimee", "disponible"}:
        raise HTTPException(status_code=403, detail="Vérification requise")

    items = (
        db.query(models.RessourceMembre)
        .filter(models.RessourceMembre.is_published.is_(True))
        .order_by(models.RessourceMembre.created_at.desc())
        .all()
    )
    return {
        "results": [
            {
                "id": r.id,
                "titre": r.titre,
                "description": r.description,
                "created_at": r.created_at.isoformat(),
            }
            for r in items
        ]
    }


@router.get("/ressources/{ressource_id}/fichier")
def ressource_fichier(
    ressource_id: int,
    numero_carte: str,
    date_naissance: str,
    db: Session = Depends(get_db),
):
    carte = _find_carte(db, numero_carte, date_naissance)
    if not carte or carte.status not in {"validee", "imprimee", "disponible"}:
        raise HTTPException(status_code=403, detail="Vérification requise")

    ressource = db.get(models.RessourceMembre, ressource_id)
    if not ressource or not ressource.is_published:
        raise HTTPException(status_code=404, detail="Ressource introuvable")
    stored = storage.get_stored_file(db, ressource.file_path)
    if not stored:
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    return Response(
        content=stored.data,
        media_type=stored.content_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_content_disposition(ressource.original_filename)}"'},
    )
