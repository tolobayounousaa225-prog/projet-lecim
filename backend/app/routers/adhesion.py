import datetime
import secrets

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..attestations_pdf import generate_adhesion_certificat_pdf, generate_adhesion_recepisse_pdf
from ..database import get_db
from ..notifications import notify_adhesion_examinateurs, notify_delegation_titulaire
from ..rate_limit import rate_limiter

router = APIRouter(prefix="/api/adhesion-requests", tags=["adhesion"])


def _get_by_code_or_404(code: str, db: Session) -> models.AdhesionRequest:
    demande = db.query(models.AdhesionRequest).filter(models.AdhesionRequest.code_demande == code).first()
    if not demande:
        raise HTTPException(status_code=404, detail="Demande introuvable")
    return demande


@router.post("", response_model=schemas.AdhesionRequestOut, status_code=status.HTTP_201_CREATED)
def submit_adhesion_request(payload: schemas.AdhesionRequestCreate, db: Session = Depends(get_db)):
    delegation = db.get(models.Delegation, payload.delegation_id)
    if not delegation:
        raise HTTPException(status_code=400, detail="Délégation sélectionnée introuvable")

    request = models.AdhesionRequest(**payload.model_dump())
    db.add(request)
    db.flush()
    # Suffixe aléatoire non devinable : un identifiant purement séquentiel permettrait
    # d'énumérer /recepisse.pdf (endpoint public, sans authentification) pour aspirer
    # les coordonnées personnelles de tout demandeur.
    request.code_demande = f"ADH-{datetime.date.today().year}-{request.id:05d}-{secrets.token_hex(3).upper()}"

    # Route la demande vers le président de la délégation choisie pour un
    # premier avis ; si son compte n'est pas encore actif, le BEN est notifié
    # directement pour ne pas bloquer le dossier (voir note sur le récépissé).
    delegation_compte_actif = notify_delegation_titulaire(
        db, delegation.id,
        f"Nouvelle demande d'adhésion à examiner : {request.nom_etablissement} ({request.localite}).",
        link=f"/delegation/adhesions/{request.id}",
    )
    if not delegation_compte_actif:
        notify_adhesion_examinateurs(
            db,
            f"Nouvelle demande d'adhésion de {request.nom_etablissement} — "
            f"la délégation « {delegation.nom} » n'a pas de compte actif, examen direct requis.",
            link=f"/admin/adhesion-requests/{request.id}",
        )

    db.commit()
    db.refresh(request)
    request.delegation_compte_actif = delegation_compte_actif
    return request


@router.get("/{code}/recepisse.pdf", dependencies=[Depends(rate_limiter("adhesion-recepisse", 20, 60))])
def download_recepisse(code: str, db: Session = Depends(get_db)):
    demande = _get_by_code_or_404(code, db)
    pdf_bytes = generate_adhesion_recepisse_pdf(demande)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="recepisse_{demande.code_demande}.pdf"'},
    )


@router.get("/{code}/certificat.pdf")
def download_certificat(code: str, db: Session = Depends(get_db)):
    demande = _get_by_code_or_404(code, db)
    if demande.etat_demande != "validee":
        raise HTTPException(status_code=403, detail="Cette demande n'est pas encore validée")
    pdf_bytes = generate_adhesion_certificat_pdf(demande)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="certificat_adhesion_{demande.code_demande}.pdf"'},
    )
