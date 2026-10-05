import datetime
import io
import re
import secrets
from pathlib import Path

import qrcode
from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import audit, models, storage
from ..config import settings
from ..database import get_db
from ..deps import require_membres_access_web, require_reunions_access_web
from ..email_utils import send_email
from ..postes import POSTES
from ..reminders import send_reminder_for_reunion
from ..reports import export_membres_xlsx
from .admin_files import ALLOWED_PHOTO_EXT

router = APIRouter(prefix="/admin", tags=["admin-reunions"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

MEMBRES_PHOTOS_DIR = "membres"


# ---------- Membres (répertoire permanent) ----------

@router.get("/membres")
def membres_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_membres_access_web),
):
    items = (
        db.query(models.Membre)
        .filter(models.Membre.delegation_id.is_(None))
        .order_by(models.Membre.full_name)
        .all()
    )

    # Statistiques d'assiduite aux reunions nationales — un membre n'a de taux
    # significatif que par rapport aux reunions tenues depuis son arrivee au bureau,
    # donc on ne compte que celles a partir de sa date d'ajout au repertoire.
    total_reunions_nationales = (
        db.query(models.Reunion).filter(models.Reunion.delegation_id.is_(None)).count()
    )
    assiduite = {}
    for item in items:
        reunions_eligibles = (
            db.query(models.Reunion)
            .filter(models.Reunion.delegation_id.is_(None), models.Reunion.created_at >= item.created_at)
            .count()
        ) if total_reunions_nationales else 0
        presences = (
            db.query(models.Presence)
            .join(models.Reunion, models.Reunion.id == models.Presence.reunion_id)
            .filter(
                models.Presence.membre_id == item.id,
                models.Presence.present.is_(True),
                models.Reunion.delegation_id.is_(None),
            )
            .count()
        )
        taux = round(presences / reunions_eligibles * 100) if reunions_eligibles else None
        assiduite[item.id] = {"reunions": reunions_eligibles, "presences": presences, "taux": taux}

    return templates.TemplateResponse(
        request,
        "admin/membres_list.html",
        {"admin": user, "items": items, "assiduite": assiduite, "active": "membres"},
    )


@router.get("/membres/new")
def membres_new_form(
    request: Request,
    user: models.User = Depends(require_membres_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/membre_form.html",
        {"admin": user, "item": None, "postes": POSTES, "active": "membres"},
    )


async def _handle_membre_photo(
    request: Request,
    photo: UploadFile | None,
    user: models.User,
    item: models.Membre | None,
    db: Session,
):
    """Sauvegarde une photo uploadée pour un membre. Retourne (chemin_relatif, réponse_erreur_ou_None)."""
    if photo is None or not photo.filename:
        return None, None
    try:
        stored_name, _ = await storage.save_upload(db, photo, MEMBRES_PHOTOS_DIR, ALLOWED_PHOTO_EXT)
        return f"{MEMBRES_PHOTOS_DIR}/{stored_name}", None
    except ValueError as exc:
        error_response = templates.TemplateResponse(
            request,
            "admin/membre_form.html",
            {"admin": user, "item": item, "postes": POSTES, "active": "membres", "error": str(exc)},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
        return None, error_response


@router.post("/membres/new")
async def membres_create(
    request: Request,
    full_name: str = Form(...),
    poste: str = Form(""),
    is_adjoint: bool = Form(False),
    phone: str = Form(""),
    email: str = Form(""),
    mandat_debut: str = Form(""),
    mandat_fin: str = Form(""),
    photo: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_membres_access_web),
):
    photo_path, error = await _handle_membre_photo(request, photo, user, None, db)
    if error:
        return error

    membre = models.Membre(
        full_name=full_name,
        poste=poste or None,
        is_adjoint=is_adjoint,
        phone=phone or None,
        email=email or None,
        mandat_debut=datetime.date.fromisoformat(mandat_debut) if mandat_debut else None,
        mandat_fin=datetime.date.fromisoformat(mandat_fin) if mandat_fin else None,
        photo_path=photo_path,
    )
    db.add(membre)
    db.commit()
    return RedirectResponse(url="/admin/membres", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/membres/{membre_id}/edit")
def membres_edit_form(
    membre_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_membres_access_web),
):
    item = db.get(models.Membre, membre_id)
    return templates.TemplateResponse(
        request,
        "admin/membre_form.html",
        {"admin": user, "item": item, "postes": POSTES, "active": "membres"},
    )


@router.post("/membres/{membre_id}/edit")
async def membres_update(
    membre_id: int,
    request: Request,
    full_name: str = Form(...),
    poste: str = Form(""),
    is_adjoint: bool = Form(False),
    phone: str = Form(""),
    email: str = Form(""),
    mandat_debut: str = Form(""),
    mandat_fin: str = Form(""),
    photo: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_membres_access_web),
):
    membre = db.get(models.Membre, membre_id)
    if membre:
        photo_path, error = await _handle_membre_photo(request, photo, user, membre, db)
        if error:
            return error
        membre.full_name = full_name
        membre.poste = poste or None
        membre.is_adjoint = is_adjoint
        membre.phone = phone or None
        membre.email = email or None
        new_mandat_fin = datetime.date.fromisoformat(mandat_fin) if mandat_fin else None
        if new_mandat_fin != membre.mandat_fin:
            membre.mandat_alert_sent = False
        membre.mandat_debut = datetime.date.fromisoformat(mandat_debut) if mandat_debut else None
        membre.mandat_fin = new_mandat_fin
        if photo_path:
            membre.photo_path = photo_path
        db.commit()
    return RedirectResponse(url="/admin/membres", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/membres/{membre_id}/delete")
def membres_delete(
    membre_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_membres_access_web),
):
    membre = db.get(models.Membre, membre_id)
    if membre:
        # Presence.membre_id n'a pas de cascade en base — une présence n'a de sens
        # que rattachée à un membre existant, donc on la nettoie explicitement
        # avant de supprimer le membre (sinon la suppression plante avec une
        # IntegrityError dès que le membre a été convoqué à au moins une réunion).
        db.query(models.Presence).filter(models.Presence.membre_id == membre_id).delete()
        db.delete(membre)
        db.commit()
    return RedirectResponse(url="/admin/membres", status_code=status.HTTP_303_SEE_OTHER)


def _vcard_escape(text: str) -> str:
    return re.sub(r"([,;\\])", r"\\\1", text).replace("\n", "\\n")


@router.get("/membres/export.vcf")
def membres_export_vcf(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_membres_access_web),
):
    """Carnet de contacts du bureau au format vCard — usage interne uniquement (le
    téléphone/e-mail des membres n'est jamais exposé par le trombinoscope public,
    voir membres_bureau_public.py). Importable directement dans le répertoire du
    téléphone (Contacts > Importer un fichier .vcf)."""
    items = (
        db.query(models.Membre)
        .filter(models.Membre.delegation_id.is_(None))
        .order_by(models.Membre.full_name)
        .all()
    )
    cards = []
    for m in items:
        lines = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"FN:{_vcard_escape(m.full_name)}",
            f"N:{_vcard_escape(m.full_name)};;;;",
            "ORG:LECIM",
        ]
        if m.poste:
            lines.append(f"TITLE:{_vcard_escape(m.poste_label)}")
        if m.phone:
            lines.append(f"TEL;TYPE=CELL:{_vcard_escape(m.phone)}")
        if m.email:
            lines.append(f"EMAIL:{_vcard_escape(m.email)}")
        lines.append("END:VCARD")
        cards.append("\r\n".join(lines))

    vcf_content = "\r\n".join(cards) + "\r\n"
    return Response(
        content=vcf_content,
        media_type="text/vcard",
        headers={"Content-Disposition": 'attachment; filename="membres-bureau-lecim.vcf"'},
    )


@router.get("/membres/export.xlsx")
def membres_export_xlsx(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_membres_access_web),
):
    items = (
        db.query(models.Membre)
        .filter(models.Membre.delegation_id.is_(None))
        .order_by(models.Membre.full_name)
        .all()
    )
    xlsx_bytes = export_membres_xlsx(items)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="membres-bureau-lecim.xlsx"'},
    )


# ---------- Réunions ----------

@router.get("/reunions")
def reunions_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    items = (
        db.query(models.Reunion)
        .filter(models.Reunion.delegation_id.is_(None))
        .order_by(models.Reunion.date.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/reunions_list.html",
        {"admin": user, "items": items, "active": "reunions"},
    )


@router.get("/reunions/new")
def reunions_new_form(
    request: Request,
    user: models.User = Depends(require_reunions_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/reunion_form.html",
        {"admin": user, "item": None, "today": datetime.date.today(), "active": "reunions"},
    )


@router.post("/reunions/new")
def reunions_create(
    title: str = Form(...),
    date: datetime.date = Form(...),
    lieu: str = Form(""),
    ordre_du_jour: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    reunion = models.Reunion(
        title=title,
        date=date,
        lieu=lieu or None,
        ordre_du_jour=ordre_du_jour or None,
        created_by_id=user.id,
    )
    db.add(reunion)
    db.commit()
    db.refresh(reunion)
    return RedirectResponse(url=f"/admin/reunions/{reunion.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/reunions/{reunion_id}/edit")
def reunions_edit_form(
    reunion_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    item = db.get(models.Reunion, reunion_id)
    return templates.TemplateResponse(
        request,
        "admin/reunion_form.html",
        {"admin": user, "item": item, "active": "reunions"},
    )


@router.post("/reunions/{reunion_id}/edit")
def reunions_update(
    reunion_id: int,
    title: str = Form(...),
    date: datetime.date = Form(...),
    lieu: str = Form(""),
    ordre_du_jour: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    reunion = db.get(models.Reunion, reunion_id)
    if reunion:
        reunion.title = title
        reunion.date = date
        reunion.lieu = lieu or None
        reunion.ordre_du_jour = ordre_du_jour or None
        db.commit()
    return RedirectResponse(url=f"/admin/reunions/{reunion_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/reunions/{reunion_id}/delete")
def reunions_delete(
    reunion_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    reunion = db.get(models.Reunion, reunion_id)
    if reunion:
        # Les Document/Photo rattachés sont supprimés en cascade côté ORM, mais
        # leurs fichiers stockés ne le sont jamais automatiquement — on les
        # supprime explicitement pour ne pas laisser de fichiers orphelins.
        for d in reunion.documents:
            storage.delete_stored_file(db, d.file_path)
        for p in reunion.photos:
            storage.delete_stored_file(db, p.file_path)
        db.delete(reunion)
        db.commit()
    return RedirectResponse(url="/admin/reunions", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/reunions/{reunion_id}")
def reunion_detail(
    reunion_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    reunion = db.get(models.Reunion, reunion_id)
    if not reunion:
        return RedirectResponse(url="/admin/reunions", status_code=status.HTTP_303_SEE_OTHER)

    # Complète la feuille de présence pour les membres ajoutés au répertoire
    # après la création de la réunion.
    existing_membre_ids = {p.membre_id for p in reunion.presences}
    all_membres = (
        db.query(models.Membre)
        .filter(models.Membre.delegation_id.is_(None))
        .order_by(models.Membre.full_name)
        .all()
    )
    for membre in all_membres:
        if membre.id not in existing_membre_ids:
            db.add(models.Presence(reunion_id=reunion.id, membre_id=membre.id, present=False))
    db.commit()
    db.refresh(reunion)

    presences = sorted(reunion.presences, key=lambda p: p.membre.full_name)
    satisfaction = (
        db.query(models.SondageSatisfaction)
        .filter(models.SondageSatisfaction.reunion_id == reunion_id)
        .first()
    )

    return templates.TemplateResponse(
        request,
        "admin/reunion_detail.html",
        {"admin": user, "reunion": reunion, "presences": presences, "active": "reunions", "satisfaction": satisfaction},
    )


@router.get("/reunions/{reunion_id}/presentation")
def reunion_presentation(
    reunion_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    """Vue projecteur plein écran pour l'ouverture d'une réunion — ordre du jour et
    liste des présents en gros caractères, sans la barre latérale ni les formulaires
    d'édition de l'espace admin habituel. Affiche aussi un QR code de pointage de
    présence (voir checkin_public.py) — généré à la volée si cette réunion n'en a pas
    encore (réunions créées avant l'ajout de cette fonctionnalité)."""
    reunion = db.get(models.Reunion, reunion_id)
    if not reunion:
        return RedirectResponse(url="/admin/reunions", status_code=status.HTTP_303_SEE_OTHER)

    if not reunion.checkin_token:
        reunion.checkin_token = secrets.token_urlsafe(24)
        db.commit()

    presents = sorted(
        (p for p in reunion.presences if p.present),
        key=lambda p: p.membre.full_name,
    )

    return templates.TemplateResponse(
        request,
        "admin/reunion_presentation.html",
        {
            "reunion": reunion,
            "presents": presents,
            "checkin_url": f"{settings.public_base_url}/checkin/{reunion.checkin_token}",
        },
    )


@router.get("/reunions/{reunion_id}/presentation/qr.png")
def reunion_presentation_qr(
    reunion_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    reunion = db.get(models.Reunion, reunion_id)
    if not reunion or not reunion.checkin_token:
        return RedirectResponse(url="/admin/reunions", status_code=status.HTTP_303_SEE_OTHER)

    checkin_url = f"{settings.public_base_url}/checkin/{reunion.checkin_token}"
    buf = io.BytesIO()
    qrcode.make(checkin_url, border=1).save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@router.post("/reunions/{reunion_id}/rappel")
def reunion_rappel(
    reunion_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    reunion = db.get(models.Reunion, reunion_id)
    if reunion:
        envoyes = send_reminder_for_reunion(db, reunion)
        audit.log(db, user, "update", "Réunion", reunion.id, f"A envoyé un rappel pour la réunion « {reunion.title} » ({envoyes} e-mail(s))")
        db.commit()
    return RedirectResponse(url=f"/admin/reunions/{reunion_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/reunions/{reunion_id}/satisfaction/envoyer")
def reunion_satisfaction_envoyer(
    reunion_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    reunion = db.get(models.Reunion, reunion_id)
    if not reunion:
        return RedirectResponse(url="/admin/reunions", status_code=status.HTTP_303_SEE_OTHER)

    sondage = (
        db.query(models.SondageSatisfaction)
        .filter(models.SondageSatisfaction.reunion_id == reunion_id)
        .first()
    )
    if not sondage:
        sondage = models.SondageSatisfaction(
            reunion_id=reunion_id, token=secrets.token_urlsafe(24), created_by_id=user.id,
        )
        db.add(sondage)
        db.flush()

    lien = f"{settings.public_base_url}/sondage-satisfaction/{sondage.token}"
    membres = (
        db.query(models.Membre)
        .filter(models.Membre.delegation_id == reunion.delegation_id, models.Membre.email.isnot(None))
        .all()
    )
    subject = f"[LECIM] Votre avis sur « {reunion.title} »"
    body = (
        f"Bonjour,\n\nMerci d'avoir participé à la réunion « {reunion.title} » du "
        f"{reunion.date.strftime('%d/%m/%Y')}. Votre avis nous intéresse (réponse anonyme, 1 minute) :\n\n"
        f"{lien}\n\nLECIM — Ligue des Établissements Confessionnels et Madrassas de Côte d'Ivoire"
    )
    envoyes = 0
    for membre in membres:
        if send_email(membre.email, subject, body):
            envoyes += 1

    audit.log(
        db, user, "create", "Sondage satisfaction", sondage.id,
        f"A envoyé le sondage de satisfaction pour « {reunion.title} » ({envoyes} e-mail(s))",
    )
    db.commit()
    return RedirectResponse(url=f"/admin/reunions/{reunion_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/reunions/{reunion_id}/presence")
async def reunion_presence_save(
    reunion_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    form = await request.form()
    present_ids = {int(v) for k, v in form.multi_items() if k == "present"}

    presences = db.query(models.Presence).filter(models.Presence.reunion_id == reunion_id).all()
    for presence in presences:
        presence.present = presence.membre_id in present_ids
    db.commit()
    return RedirectResponse(url=f"/admin/reunions/{reunion_id}", status_code=status.HTTP_303_SEE_OTHER)
