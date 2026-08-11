import datetime
from pathlib import Path

import mimetypes

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import audit, models
from ..card_pdf import generate_card_pdf
from ..database import get_db
from ..deps import require_cartes_gestion_web, require_login_web
from ..notifications import notify, notify_cartes_gestionnaires
from .admin_files import ALLOWED_PHOTO_EXT, UPLOAD_ROOT, _save_upload

router = APIRouter(prefix="/admin", tags=["admin-cartes"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

CARTES_PHOTOS_DIR = UPLOAD_ROOT / "cartes_photos"


def _next_numero_carte(db: Session) -> str:
    count = db.query(models.CarteMembre).filter(models.CarteMembre.numero_carte.isnot(None)).count()
    return f"LECIM-{count + 1:04d}"


CARTE_VALIDITE_ANNEES = 3


def _validite_dans_n_ans(depuis: datetime.date, annees: int) -> datetime.date:
    try:
        return depuis.replace(year=depuis.year + annees)
    except ValueError:
        # 29 fevrier sur une annee non bissextile
        return depuis.replace(month=2, day=28, year=depuis.year + annees)


# ---------- Espace personnel : ma carte ----------

@router.get("/cartes/mine")
def carte_mine(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_web),
):
    carte = (
        db.query(models.CarteMembre)
        .filter(models.CarteMembre.user_id == user.id)
        .order_by(models.CarteMembre.date_soumission.desc())
        .first()
    )
    can_request = carte is None or carte.status == "rejetee"
    return templates.TemplateResponse(
        request,
        "admin/carte_mine.html",
        {
            "admin": user,
            "carte": carte,
            "can_request": can_request,
            "today": datetime.date.today(),
            "active": "carte_mine",
            "error": None,
        },
    )


@router.post("/cartes/mine/new")
async def carte_mine_create(
    request: Request,
    full_name: str = Form(...),
    date_naissance: str = Form(""),
    ville: str = Form(""),
    adresse: str = Form(""),
    telephone: str = Form(""),
    cni_numero: str = Form(""),
    contact_urgence_nom: str = Form(""),
    contact_urgence_telephone: str = Form(""),
    email_personnel: str = Form(""),
    photo: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_web),
):
    existing = (
        db.query(models.CarteMembre)
        .filter(models.CarteMembre.user_id == user.id)
        .order_by(models.CarteMembre.date_soumission.desc())
        .first()
    )
    if existing is not None and existing.status != "rejetee":
        # Une demande est déjà en cours ou aboutie : pas de nouvelle soumission tant
        # qu'elle n'a pas été rejetée (cohérent avec l'affichage du formulaire).
        return RedirectResponse(url="/admin/cartes/mine", status_code=status.HTTP_303_SEE_OTHER)

    photo_path = None
    if photo is not None and photo.filename:
        try:
            stored_name, _original = await _save_upload(photo, CARTES_PHOTOS_DIR, ALLOWED_PHOTO_EXT)
            photo_path = f"cartes_photos/{stored_name}"
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "admin/carte_mine.html",
                {
                    "admin": user,
                    "carte": None,
                    "can_request": True,
                    "today": datetime.date.today(),
                    "active": "carte_mine",
                    "error": str(exc),
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    carte = models.CarteMembre(
        user_id=user.id,
        full_name_snapshot=full_name,
        photo_path=photo_path,
        date_naissance=datetime.date.fromisoformat(date_naissance) if date_naissance else None,
        ville=ville or None,
        adresse=adresse or None,
        telephone=telephone or None,
        cni_numero=cni_numero or None,
        contact_urgence_nom=contact_urgence_nom or None,
        contact_urgence_telephone=contact_urgence_telephone or None,
        email_personnel=email_personnel or None,
        status="soumise",
    )
    db.add(carte)
    notify_cartes_gestionnaires(
        db,
        f"Nouvelle demande de carte de membre de {user.full_name} ({user.poste_label}).",
        link="/admin/cartes",
    )
    db.commit()
    return RedirectResponse(url="/admin/cartes/mine", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Gestion des cartes (secrétaire administratif) ----------

@router.get("/cartes")
def cartes_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_cartes_gestion_web),
):
    items = db.query(models.CarteMembre).order_by(models.CarteMembre.date_soumission.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin/cartes_gestion_list.html",
        {"admin": user, "items": items, "active": "cartes"},
    )


@router.get("/cartes/{carte_id}")
def carte_detail(
    carte_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_cartes_gestion_web),
):
    carte = db.get(models.CarteMembre, carte_id)
    if not carte:
        return RedirectResponse(url="/admin/cartes", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request,
        "admin/carte_detail.html",
        {"admin": user, "carte": carte, "active": "cartes"},
    )


@router.get("/cartes/{carte_id}/photo")
def carte_photo(
    carte_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_web),
):
    carte = db.get(models.CarteMembre, carte_id)
    if not carte or not carte.photo_path:
        return RedirectResponse(url="/admin/cartes", status_code=status.HTTP_303_SEE_OTHER)
    if not (user.is_admin or user.can_manage_cartes or user.id == carte.user_id):
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    path = UPLOAD_ROOT / carte.photo_path
    media_type = mimetypes.guess_type(carte.photo_path)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)


@router.post("/cartes/{carte_id}/valider")
def carte_valider(
    carte_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_cartes_gestion_web),
):
    carte = db.get(models.CarteMembre, carte_id)
    if carte and carte.status == "soumise":
        carte.status = "validee"
        carte.date_validation = datetime.datetime.utcnow()
        carte.date_validite = _validite_dans_n_ans(datetime.date.today(), CARTE_VALIDITE_ANNEES)
        carte.validated_by_id = user.id
        if not carte.numero_carte:
            carte.numero_carte = _next_numero_carte(db)
        notify(
            db,
            carte.user_id,
            "Votre demande de carte de membre a été validée — elle est en cours d'impression.",
            link="/admin/cartes/mine",
        )
        audit.log(db, user, "update", "Carte de membre", carte.id, f"A validé la carte de {carte.full_name_snapshot}")
        db.commit()
    return RedirectResponse(url=f"/admin/cartes/{carte_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/cartes/{carte_id}/rejeter")
def carte_rejeter(
    carte_id: int,
    commentaire_rejet: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_cartes_gestion_web),
):
    carte = db.get(models.CarteMembre, carte_id)
    if carte and carte.status == "soumise":
        carte.status = "rejetee"
        carte.commentaire_rejet = commentaire_rejet or None
        carte.validated_by_id = user.id
        message = "Votre demande de carte de membre a été rejetée."
        if commentaire_rejet:
            message += f" Motif : {commentaire_rejet}"
        message += " Vous pouvez soumettre une nouvelle demande."
        notify(db, carte.user_id, message, link="/admin/cartes/mine")
        audit.log(db, user, "update", "Carte de membre", carte.id, f"A rejeté la carte de {carte.full_name_snapshot}")
        db.commit()
    return RedirectResponse(url=f"/admin/cartes/{carte_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/cartes/{carte_id}/imprimer")
def carte_imprimer(
    carte_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_cartes_gestion_web),
):
    carte = db.get(models.CarteMembre, carte_id)
    if carte and carte.status == "validee":
        carte.status = "imprimee"
        carte.date_impression = datetime.datetime.utcnow()
        notify(
            db,
            carte.user_id,
            "Votre carte de membre a été imprimée.",
            link="/admin/cartes/mine",
        )
        audit.log(db, user, "update", "Carte de membre", carte.id, f"A marqué la carte de {carte.full_name_snapshot} comme imprimée")
        db.commit()
    return RedirectResponse(url=f"/admin/cartes/{carte_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/cartes/{carte_id}/disponible")
def carte_disponible(
    carte_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_cartes_gestion_web),
):
    carte = db.get(models.CarteMembre, carte_id)
    if carte and carte.status == "imprimee":
        carte.status = "disponible"
        carte.date_disponibilite = datetime.datetime.utcnow()
        notify(
            db,
            carte.user_id,
            "Votre carte de membre est disponible — vous pouvez la récupérer auprès du secrétariat.",
            link="/admin/cartes/mine",
        )
        audit.log(db, user, "update", "Carte de membre", carte.id, f"A marqué la carte de {carte.full_name_snapshot} comme disponible")
        db.commit()
    return RedirectResponse(url=f"/admin/cartes/{carte_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/cartes/{carte_id}/pdf")
def carte_pdf(
    carte_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_cartes_gestion_web),
):
    carte = db.get(models.CarteMembre, carte_id)
    if not carte or carte.status not in {"validee", "imprimee", "disponible"}:
        return RedirectResponse(url="/admin/cartes", status_code=status.HTTP_303_SEE_OTHER)
    photo_path = UPLOAD_ROOT / carte.photo_path if carte.photo_path else None
    pdf_bytes = generate_card_pdf(carte, photo_path)
    filename = f"carte_{carte.numero_carte or carte.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- Notifications ----------

@router.get("/notifications")
def notifications_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_web),
):
    items = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user.id)
        .order_by(models.Notification.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/notifications.html",
        {"admin": user, "items": items, "active": "notifications"},
    )


@router.post("/notifications/{notification_id}/read")
def notification_mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_web),
):
    notif = db.get(models.Notification, notification_id)
    if notif and notif.user_id == user.id:
        notif.is_read = True
        db.commit()
    return RedirectResponse(url="/admin/notifications", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/notifications/read-all")
def notifications_mark_all_read(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_web),
):
    db.query(models.Notification).filter(
        models.Notification.user_id == user.id, models.Notification.is_read.is_(False)
    ).update({"is_read": True})
    db.commit()
    return RedirectResponse(url="/admin/notifications", status_code=status.HTTP_303_SEE_OTHER)
