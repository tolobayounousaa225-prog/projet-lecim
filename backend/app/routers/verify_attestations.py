"""Vérification publique des attestations (affiliation établissement, appartenance BEN),
ouverte au scan du QR code — même philosophie que /verify et /verify-eleve : aucune
authentification requise, aucune donnée personnelle sensible exposée."""

import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..attestations_pdf import numero_affiliation
from ..database import get_db
from ..rate_limit import rate_limiter

router = APIRouter(tags=["verify"], dependencies=[Depends(rate_limiter("verify-attestations", 30, 60))])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/verify-etablissement/{etablissement_id}")
def verify_etablissement(etablissement_id: int, request: Request, db: Session = Depends(get_db)):
    etablissement = db.get(models.Etablissement, etablissement_id)
    return templates.TemplateResponse(
        request,
        "verify_etablissement.html",
        {
            "etablissement": etablissement,
            "found": etablissement is not None,
            "numero": numero_affiliation(etablissement_id),
        },
    )


@router.get("/verify-membre/{user_id}")
def verify_membre(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = db.get(models.User, user_id)
    is_ben_member = (
        user is not None
        and not user.is_delegation_account
        and not user.is_etablissement_account
    )
    return templates.TemplateResponse(
        request,
        "verify_membre.html",
        {"user": user if is_ben_member else None, "found": is_ben_member},
    )


@router.get("/verify-adhesion/{code}")
def verify_adhesion(code: str, request: Request, db: Session = Depends(get_db)):
    demande = db.query(models.AdhesionRequest).filter(models.AdhesionRequest.code_demande == code).first()
    return templates.TemplateResponse(
        request,
        "verify_adhesion.html",
        {"demande": demande, "found": demande is not None},
    )


@router.get("/verify-rapport/{code}")
def verify_rapport(code: str, request: Request, db: Session = Depends(get_db)):
    rapport = db.query(models.RapportGenere).filter(models.RapportGenere.code == code).first()
    return templates.TemplateResponse(
        request,
        "verify_rapport.html",
        {"rapport": rapport, "found": rapport is not None},
    )


@router.get("/verify-diplome/{numero_diplome}")
def verify_diplome(numero_diplome: str, request: Request, db: Session = Depends(get_db)):
    diplome = db.query(models.Diplome).filter(models.Diplome.numero_diplome == numero_diplome).first()
    return templates.TemplateResponse(
        request,
        "verify_diplome.html",
        {"diplome": diplome, "found": diplome is not None},
    )


def _age(date_naissance: datetime.date | None) -> int | None:
    if not date_naissance:
        return None
    today = datetime.date.today()
    years = today.year - date_naissance.year
    if (today.month, today.day) < (date_naissance.month, date_naissance.day):
        years -= 1
    return years


def _diplome_out(d: "models.Diplome") -> dict:
    return {
        "numero_diplome": d.numero_diplome,
        "nom_complet": d.nom_complet,
        "etablissement_nom": d.etablissement_nom,
        "type_examen": d.type_examen,
        "mention": d.mention,
        "annee_scolaire": d.annee_scolaire,
        "date_delivrance": d.date_delivrance.isoformat(),
        "age": _age(d.date_naissance),
    }


@router.get("/api/diplomes/verifier")
def verifier_diplome(
    numero: str | None = None,
    nom_complet: str | None = None,
    date_naissance: str | None = None,
    db: Session = Depends(get_db),
):
    """Recherche publique côté site vitrine — un visiteur peut vérifier un diplôme
    soit par son numéro, soit par le nom complet ET la date de naissance exacts du
    titulaire (les deux ensemble : jamais le nom seul, qui transformerait cette
    route en annuaire public consultable par simple essai-erreur sur des noms)."""
    results: list[models.Diplome] = []

    numero = (numero or "").strip()
    if numero:
        diplome = db.query(models.Diplome).filter(models.Diplome.numero_diplome == numero).first()
        if diplome:
            results = [diplome]
    elif nom_complet and date_naissance:
        try:
            parsed_naissance = datetime.datetime.strptime(date_naissance.strip(), "%Y-%m-%d").date()
        except ValueError:
            parsed_naissance = None
        nom_clean = nom_complet.strip()
        if parsed_naissance and nom_clean:
            results = (
                db.query(models.Diplome)
                .filter(
                    func.lower(func.trim(models.Diplome.nom_complet)) == nom_clean.lower(),
                    models.Diplome.date_naissance == parsed_naissance,
                )
                .all()
            )

    return {"results": [_diplome_out(d) for d in results]}
