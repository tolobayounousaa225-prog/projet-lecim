import datetime
import mimetypes
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .. import audit, models
from ..card_pdf import generate_student_card_pdf
from ..database import get_db
from ..deps import require_cartes_scolaires_access_web
from ..notifications import notify
from .admin_files import UPLOAD_ROOT

router = APIRouter(prefix="/admin/cartes-scolaires", tags=["admin-cartes-scolaires"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

CARTE_VALIDITE_ANNEES = 1


def _next_matricule(db: Session) -> str:
    """Matricule imprévisible (espace aléatoire) — un matricule séquentiel
    permettrait d'énumérer /verify-eleve/{matricule}/photo et d'aspirer les photos
    et identités de tous les élèves. Contrainte d'unicité en base en filet final."""
    for _ in range(10):
        candidate = f"LECIM-EL-{secrets.token_hex(4).upper()}"
        exists = db.query(models.CarteScolaire.id).filter(models.CarteScolaire.matricule == candidate).first()
        if not exists:
            return candidate
    raise RuntimeError("Impossible de générer un matricule disponible")


def _validite_dans_n_ans(depuis: datetime.date, annees: int) -> datetime.date:
    try:
        return depuis.replace(year=depuis.year + annees)
    except ValueError:
        return depuis.replace(month=2, day=28, year=depuis.year + annees)


@router.get("")
def cartes_scolaires_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_cartes_scolaires_access_web),
):
    items = (
        db.query(models.CarteScolaire)
        .options(joinedload(models.CarteScolaire.etablissement))
        .order_by(models.CarteScolaire.date_soumission.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/cartes_scolaires_list.html",
        {"admin": user, "items": items, "active": "cartes_scolaires"},
    )


@router.get("/{carte_id}")
def carte_scolaire_detail(
    carte_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_cartes_scolaires_access_web),
):
    carte = db.get(models.CarteScolaire, carte_id)
    if not carte:
        return RedirectResponse(url="/admin/cartes-scolaires", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request,
        "admin/carte_scolaire_detail.html",
        {"admin": user, "carte": carte, "active": "cartes_scolaires"},
    )


@router.get("/{carte_id}/photo")
def carte_scolaire_photo(
    carte_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_cartes_scolaires_access_web),
):
    carte = db.get(models.CarteScolaire, carte_id)
    if not carte or not carte.photo_path:
        return RedirectResponse(url="/admin/cartes-scolaires", status_code=status.HTTP_303_SEE_OTHER)
    path = UPLOAD_ROOT / carte.photo_path
    media_type = mimetypes.guess_type(carte.photo_path)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)


@router.post("/{carte_id}/valider")
def carte_scolaire_valider(
    carte_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_cartes_scolaires_access_web),
):
    carte = db.get(models.CarteScolaire, carte_id)
    if carte and carte.status == "soumise":
        carte.status = "validee"
        carte.date_validation = datetime.datetime.utcnow()
        carte.date_validite = _validite_dans_n_ans(datetime.date.today(), CARTE_VALIDITE_ANNEES)
        carte.validated_by_id = user.id
        if not carte.matricule:
            carte.matricule = _next_matricule(db)
        if carte.requested_by_id:
            notify(
                db, carte.requested_by_id,
                f"La carte scolaire de {carte.eleve_nom} a été validée — elle est en cours d'impression.",
                link="/etablissement/cartes-scolaires",
            )
        audit.log(db, user, "update", "Carte scolaire", carte.id, f"A validé la carte scolaire de {carte.eleve_nom} ({carte.etablissement.nom})")
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if carte.requested_by_id:
                notify(db, carte.requested_by_id, "Conflit sur le matricule généré — veuillez réessayer la validation.", link=f"/admin/cartes-scolaires/{carte_id}")
                db.commit()
    return RedirectResponse(url=f"/admin/cartes-scolaires/{carte_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{carte_id}/rejeter")
def carte_scolaire_rejeter(
    carte_id: int,
    commentaire_rejet: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_cartes_scolaires_access_web),
):
    carte = db.get(models.CarteScolaire, carte_id)
    if carte and carte.status == "soumise":
        carte.status = "rejetee"
        carte.commentaire_rejet = commentaire_rejet or None
        carte.validated_by_id = user.id
        if carte.requested_by_id:
            message = f"La demande de carte scolaire de {carte.eleve_nom} a été rejetée."
            if commentaire_rejet:
                message += f" Motif : {commentaire_rejet}"
            notify(db, carte.requested_by_id, message, link="/etablissement/cartes-scolaires")
        audit.log(db, user, "update", "Carte scolaire", carte.id, f"A rejeté la carte scolaire de {carte.eleve_nom} ({carte.etablissement.nom})")
        db.commit()
    return RedirectResponse(url=f"/admin/cartes-scolaires/{carte_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{carte_id}/imprimer")
def carte_scolaire_imprimer(
    carte_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_cartes_scolaires_access_web),
):
    carte = db.get(models.CarteScolaire, carte_id)
    if carte and carte.status == "validee":
        carte.status = "imprimee"
        carte.date_impression = datetime.datetime.utcnow()
        if carte.requested_by_id:
            notify(db, carte.requested_by_id, f"La carte scolaire de {carte.eleve_nom} a été imprimée.", link="/etablissement/cartes-scolaires")
        audit.log(db, user, "update", "Carte scolaire", carte.id, f"A marqué la carte scolaire de {carte.eleve_nom} comme imprimée")
        db.commit()
    return RedirectResponse(url=f"/admin/cartes-scolaires/{carte_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{carte_id}/disponible")
def carte_scolaire_disponible(
    carte_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_cartes_scolaires_access_web),
):
    carte = db.get(models.CarteScolaire, carte_id)
    if carte and carte.status == "imprimee":
        carte.status = "disponible"
        carte.date_disponibilite = datetime.datetime.utcnow()
        if carte.requested_by_id:
            notify(
                db, carte.requested_by_id,
                f"La carte scolaire de {carte.eleve_nom} est disponible — elle peut être récupérée auprès du secrétariat.",
                link="/etablissement/cartes-scolaires",
            )
        audit.log(db, user, "update", "Carte scolaire", carte.id, f"A marqué la carte scolaire de {carte.eleve_nom} comme disponible")
        db.commit()
    return RedirectResponse(url=f"/admin/cartes-scolaires/{carte_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{carte_id}/pdf")
def carte_scolaire_pdf(
    carte_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_cartes_scolaires_access_web),
):
    carte = db.get(models.CarteScolaire, carte_id)
    if not carte or carte.status not in {"validee", "imprimee", "disponible"}:
        return RedirectResponse(url="/admin/cartes-scolaires", status_code=status.HTTP_303_SEE_OTHER)
    photo_path = UPLOAD_ROOT / carte.photo_path if carte.photo_path else None
    logo_path = UPLOAD_ROOT / carte.etablissement.logo_path if carte.etablissement.logo_path else None
    pdf_bytes = generate_student_card_pdf(carte, photo_path, logo_path)
    filename = f"carte_scolaire_{carte.matricule or carte.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
