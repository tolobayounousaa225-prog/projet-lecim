"""Résultats publics aux examens scolaires islamiques, par établissement et année scolaire."""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/resultats-examens", tags=["resultats-examens"])


@router.get("", response_model=list[schemas.ResultatExamenOut])
def list_resultats(
    etablissement_id: int | None = None,
    annee_scolaire: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.ResultatExamen).filter(models.ResultatExamen.is_published.is_(True))
    if etablissement_id:
        query = query.filter(models.ResultatExamen.etablissement_id == etablissement_id)
    if annee_scolaire:
        query = query.filter(models.ResultatExamen.annee_scolaire == annee_scolaire)
    return query.order_by(models.ResultatExamen.annee_scolaire.desc()).all()


def _taux(admis: int, inscrits: int) -> float:
    return round(admis / inscrits * 100, 1) if inscrits else 0.0


@router.get("/baremetre", response_model=schemas.BaremetreOut)
def baremetre(db: Session = Depends(get_db)):
    """Vue agrégée (nationale et régionale) des résultats aux examens, distincte de
    la liste établissement par établissement — pour donner une vue d'ensemble."""
    national_rows = (
        db.query(
            models.ResultatExamen.annee_scolaire,
            models.ResultatExamen.type_examen,
            func.coalesce(func.sum(models.ResultatExamen.nombre_inscrits), 0).label("inscrits"),
            func.coalesce(func.sum(models.ResultatExamen.nombre_admis), 0).label("admis"),
        )
        .filter(models.ResultatExamen.is_published.is_(True))
        .group_by(models.ResultatExamen.annee_scolaire, models.ResultatExamen.type_examen)
        .order_by(models.ResultatExamen.annee_scolaire.desc(), models.ResultatExamen.type_examen)
        .all()
    )
    national = [
        schemas.BaremetreAnneeOut(
            annee_scolaire=r.annee_scolaire,
            type_examen=r.type_examen,
            inscrits=r.inscrits,
            admis=r.admis,
            taux_reussite=_taux(r.admis, r.inscrits),
        )
        for r in national_rows
    ]

    regional_rows = (
        db.query(
            models.ResultatExamen.annee_scolaire,
            models.Etablissement.bureau_local,
            func.coalesce(func.sum(models.ResultatExamen.nombre_inscrits), 0).label("inscrits"),
            func.coalesce(func.sum(models.ResultatExamen.nombre_admis), 0).label("admis"),
        )
        .join(models.Etablissement, models.Etablissement.id == models.ResultatExamen.etablissement_id)
        .filter(models.ResultatExamen.is_published.is_(True), models.Etablissement.bureau_local.isnot(None))
        .group_by(models.ResultatExamen.annee_scolaire, models.Etablissement.bureau_local)
        .order_by(models.ResultatExamen.annee_scolaire.desc(), models.Etablissement.bureau_local)
        .all()
    )
    regional = [
        schemas.BaremetreRegionOut(
            annee_scolaire=r.annee_scolaire,
            bureau_local=r.bureau_local,
            inscrits=r.inscrits,
            admis=r.admis,
            taux_reussite=_taux(r.admis, r.inscrits),
        )
        for r in regional_rows
    ]

    return schemas.BaremetreOut(national=national, regional=regional)
