import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_executif_access_web
from ..reports import (
    _period_data,
    _solde_cumule_au,
    current_annee_scolaire,
    etablissements_en_retard,
    generate_annual_report_pdf,
    money,
)

router = APIRouter(prefix="/admin/executif", tags=["admin-executif"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("")
def executif_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_executif_access_web),
):
    today = datetime.date.today()
    debut_annee = datetime.date(today.year if today.month >= 9 else today.year - 1, 9, 1)

    finances = _period_data(db, debut_annee, today)
    solde_cumule = _solde_cumule_au(db, today)
    en_retard = etablissements_en_retard(db)

    mandats_a_surveiller = [
        m
        for m in db.query(models.Membre).filter(models.Membre.delegation_id.is_(None)).all()
        if m.mandat_status in ("expire", "bientot")
    ]

    reunions_nationales = (
        db.query(models.Reunion).filter(models.Reunion.delegation_id.is_(None)).count()
    )
    reunions_locales = (
        db.query(models.Reunion).filter(models.Reunion.delegation_id.isnot(None)).count()
    )
    membres_ben = db.query(models.Membre).filter(models.Membre.delegation_id.is_(None)).count()
    membres_locaux = db.query(models.Membre).filter(models.Membre.delegation_id.isnot(None)).count()

    cartes = {
        "soumise": db.query(models.CarteMembre).filter(models.CarteMembre.status == "soumise").count(),
        "validee": db.query(models.CarteMembre).filter(models.CarteMembre.status == "validee").count(),
        "imprimee": db.query(models.CarteMembre).filter(models.CarteMembre.status == "imprimee").count(),
        "disponible": db.query(models.CarteMembre).filter(models.CarteMembre.status == "disponible").count(),
    }

    partenaires_actifs = db.query(models.Partenaire).filter(models.Partenaire.statut == "actif").count()
    partenaires_total = db.query(models.Partenaire).count()

    projets_en_cours = db.query(models.Projet).filter(models.Projet.statut == "en_cours").count()
    projets_total = db.query(models.Projet).count()
    patrimoine_total = db.query(models.Patrimoine).count()

    demandes_en_attente = (
        db.query(models.DemandeAssistance)
        .filter(models.DemandeAssistance.statut.in_(["nouvelle", "en_cours"]))
        .count()
    )
    demandes_total = db.query(models.DemandeAssistance).count()

    documents_total = db.query(models.Document).count()
    publications_total = db.query(models.PublicationPublique).count()
    etablissements_total = db.query(models.Etablissement).count()

    delegations = db.query(models.Delegation).order_by(models.Delegation.nom).all()
    delegations_comptes = db.query(models.User).filter(models.User.delegation_id.isnot(None)).count()

    return templates.TemplateResponse(
        request,
        "admin/executif_dashboard.html",
        {
            "admin": user,
            "active": "executif",
            "annee_scolaire": current_annee_scolaire(),
            "finances": finances,
            "solde_cumule": solde_cumule,
            "en_retard_count": len(en_retard),
            "mandats_a_surveiller": mandats_a_surveiller,
            "reunions_nationales": reunions_nationales,
            "reunions_locales": reunions_locales,
            "membres_ben": membres_ben,
            "membres_locaux": membres_locaux,
            "cartes": cartes,
            "partenaires_actifs": partenaires_actifs,
            "partenaires_total": partenaires_total,
            "projets_en_cours": projets_en_cours,
            "projets_total": projets_total,
            "patrimoine_total": patrimoine_total,
            "demandes_en_attente": demandes_en_attente,
            "demandes_total": demandes_total,
            "documents_total": documents_total,
            "publications_total": publications_total,
            "etablissements_total": etablissements_total,
            "delegations": delegations,
            "delegations_comptes": delegations_comptes,
            "money": money,
        },
    )


@router.get("/rapport-annuel")
def executif_rapport_annuel(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_executif_access_web),
):
    today = datetime.date.today()
    annee_scolaire = current_annee_scolaire()
    debut_annee = datetime.date(today.year if today.month >= 9 else today.year - 1, 9, 1)

    pdf_bytes = generate_annual_report_pdf(db, annee_scolaire, debut_annee, today, user.full_name)
    filename = f"lecim-rapport-annuel-{annee_scolaire}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
