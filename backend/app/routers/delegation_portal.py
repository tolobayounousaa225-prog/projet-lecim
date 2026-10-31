import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import audit, models, storage
from ..database import get_db
from ..deps import (
    require_delegation_annonces_web,
    require_delegation_cotisations_web,
    require_delegation_documents_web,
    require_delegation_etablissements_web,
    require_delegation_login_web,
    require_delegation_membres_web,
    require_delegation_messagerie_web,
    require_delegation_rapport_web,
    require_delegation_reunions_web,
)
from ..finances_constants import cotisation_rule
from ..notifications import notify
from ..reminders import send_reminder_for_reunion
from ..security import hash_password, password_policy_error, verify_password
from ..security_utils import safe_content_disposition

DOCUMENTS_DELEGATION_DIR = "documents_delegations"

router = APIRouter(tags=["delegation-portal"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


# ---------- Connexion ----------

@router.get("/delegation/login")
def delegation_login_page(request: Request):
    return templates.TemplateResponse(request, "delegation_login.html", {"error": None})


@router.get("/delegation/logout")
def delegation_logout():
    response = RedirectResponse(url="/delegation/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response


# ---------- Tableau de bord ----------

@router.get("/delegation")
def delegation_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_login_web),
):
    delegation_id = user.delegation_id
    counts = {
        "reunions": db.query(models.Reunion).filter(models.Reunion.delegation_id == delegation_id).count(),
        "membres": db.query(models.Membre).filter(models.Membre.delegation_id == delegation_id).count(),
        "etablissements": db.query(models.Etablissement)
        .filter(models.Etablissement.delegation_id == delegation_id)
        .count(),
    }

    reunions = (
        db.query(models.Reunion)
        .filter(models.Reunion.delegation_id == delegation_id)
        .order_by(models.Reunion.date.desc())
        .all()
    )
    total_presences = 0
    total_presents = 0
    for r in reunions:
        total_presences += len(r.presences)
        total_presents += sum(1 for p in r.presences if p.present)
    taux_presence = round((total_presents / total_presences) * 100, 1) if total_presences else None

    derniere_reunion = reunions[0] if reunions else None
    prochaine_reunion = (
        db.query(models.Reunion)
        .filter(models.Reunion.delegation_id == delegation_id, models.Reunion.date >= datetime.date.today())
        .order_by(models.Reunion.date)
        .first()
    )

    jours_sans_reunion = (
        (datetime.date.today() - derniere_reunion.date).days if derniere_reunion else None
    )
    alerte_inactivite = jours_sans_reunion is not None and jours_sans_reunion > 90

    unread_messages = user.unread_messages_count

    return templates.TemplateResponse(
        request,
        "delegation/dashboard.html",
        {
            "user": user,
            "delegation": user.delegation,
            "counts": counts,
            "taux_presence": taux_presence,
            "derniere_reunion": derniere_reunion,
            "prochaine_reunion": prochaine_reunion,
            "jours_sans_reunion": jours_sans_reunion,
            "alerte_inactivite": alerte_inactivite,
            "unread_messages": unread_messages,
            "active": "dashboard",
        },
    )


# ---------- Mon compte ----------

@router.get("/delegation/mon-compte/mot-de-passe")
def delegation_change_password_page(
    request: Request,
    user: models.User = Depends(require_delegation_login_web),
):
    return templates.TemplateResponse(
        request,
        "delegation/change_password.html",
        {"user": user, "delegation": user.delegation, "active": "mon_compte", "error": None, "success": None},
    )


@router.post("/delegation/mon-compte/mot-de-passe")
def delegation_change_password_submit(
    request: Request,
    mot_de_passe_actuel: str = Form(...),
    nouveau_mot_de_passe: str = Form(...),
    confirmation: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_login_web),
):
    error = None
    if not verify_password(mot_de_passe_actuel, user.hashed_password):
        error = "Mot de passe actuel incorrect."
    elif nouveau_mot_de_passe != confirmation:
        error = "Les deux mots de passe ne correspondent pas."
    else:
        error = password_policy_error(nouveau_mot_de_passe)

    if error:
        return templates.TemplateResponse(
            request,
            "delegation/change_password.html",
            {"user": user, "delegation": user.delegation, "active": "mon_compte", "error": error, "success": None},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user.hashed_password = hash_password(nouveau_mot_de_passe)
    db.query(models.PasswordResetRequest).filter(
        models.PasswordResetRequest.user_id == user.id, models.PasswordResetRequest.used.is_(False)
    ).update({"used": True})
    audit.log(db, user, "update", "Mot de passe", user.id, f"{user.full_name} a changé son mot de passe")
    db.commit()
    return templates.TemplateResponse(
        request,
        "delegation/change_password.html",
        {"user": user, "delegation": user.delegation, "active": "mon_compte", "error": None, "success": "Mot de passe mis à jour."},
    )


# ---------- Réunions locales ----------

@router.get("/delegation/reunions")
def delegation_reunions_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_reunions_web),
):
    items = (
        db.query(models.Reunion)
        .filter(models.Reunion.delegation_id == user.delegation_id)
        .order_by(models.Reunion.date.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "delegation/reunions_list.html",
        {"user": user, "delegation": user.delegation, "items": items, "active": "reunions"},
    )


@router.get("/delegation/reunions/new")
def delegation_reunions_new_form(
    request: Request,
    user: models.User = Depends(require_delegation_reunions_web),
):
    return templates.TemplateResponse(
        request,
        "delegation/reunion_form.html",
        {"user": user, "delegation": user.delegation, "item": None, "today": datetime.date.today(), "active": "reunions"},
    )


@router.post("/delegation/reunions/new")
def delegation_reunions_create(
    title: str = Form(...),
    date: datetime.date = Form(...),
    lieu: str = Form(""),
    ordre_du_jour: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_reunions_web),
):
    reunion = models.Reunion(
        title=title,
        date=date,
        lieu=lieu or None,
        ordre_du_jour=ordre_du_jour or None,
        created_by_id=user.id,
        delegation_id=user.delegation_id,
    )
    db.add(reunion)
    db.commit()
    db.refresh(reunion)
    return RedirectResponse(url=f"/delegation/reunions/{reunion.id}", status_code=status.HTTP_303_SEE_OTHER)


def _get_scoped_reunion(db: Session, user: models.User, reunion_id: int) -> models.Reunion | None:
    reunion = db.get(models.Reunion, reunion_id)
    if reunion and reunion.delegation_id == user.delegation_id:
        return reunion
    return None


@router.get("/delegation/reunions/{reunion_id}")
def delegation_reunion_detail(
    reunion_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_reunions_web),
):
    reunion = _get_scoped_reunion(db, user, reunion_id)
    if not reunion:
        return RedirectResponse(url="/delegation/reunions", status_code=status.HTTP_303_SEE_OTHER)

    existing_membre_ids = {p.membre_id for p in reunion.presences}
    all_membres = (
        db.query(models.Membre)
        .filter(models.Membre.delegation_id == user.delegation_id)
        .order_by(models.Membre.full_name)
        .all()
    )
    for membre in all_membres:
        if membre.id not in existing_membre_ids:
            db.add(models.Presence(reunion_id=reunion.id, membre_id=membre.id, present=False))
    db.commit()
    db.refresh(reunion)

    presences = sorted(reunion.presences, key=lambda p: p.membre.full_name)
    return templates.TemplateResponse(
        request,
        "delegation/reunion_detail.html",
        {"user": user, "delegation": user.delegation, "reunion": reunion, "presences": presences, "active": "reunions"},
    )


@router.post("/delegation/reunions/{reunion_id}/rappel")
def delegation_reunion_rappel(
    reunion_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_reunions_web),
):
    reunion = _get_scoped_reunion(db, user, reunion_id)
    if reunion:
        send_reminder_for_reunion(db, reunion)
    return RedirectResponse(url=f"/delegation/reunions/{reunion_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/delegation/reunions/{reunion_id}/presence")
async def delegation_reunion_presence_save(
    reunion_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_reunions_web),
):
    reunion = _get_scoped_reunion(db, user, reunion_id)
    if not reunion:
        return RedirectResponse(url="/delegation/reunions", status_code=status.HTTP_303_SEE_OTHER)
    form = await request.form()
    present_ids = {int(v) for k, v in form.multi_items() if k == "present"}
    for presence in reunion.presences:
        presence.present = presence.membre_id in present_ids
    db.commit()
    return RedirectResponse(url=f"/delegation/reunions/{reunion_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/delegation/reunions/{reunion_id}/delete")
def delegation_reunion_delete(
    reunion_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_reunions_web),
):
    reunion = _get_scoped_reunion(db, user, reunion_id)
    if reunion:
        db.delete(reunion)
        db.commit()
    return RedirectResponse(url="/delegation/reunions", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Répertoire local des membres ----------

@router.get("/delegation/membres")
def delegation_membres_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_membres_web),
):
    items = (
        db.query(models.Membre)
        .filter(models.Membre.delegation_id == user.delegation_id)
        .order_by(models.Membre.full_name)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "delegation/membres_list.html",
        {"user": user, "delegation": user.delegation, "items": items, "active": "membres"},
    )


@router.get("/delegation/membres/new")
def delegation_membres_new_form(
    request: Request,
    user: models.User = Depends(require_delegation_membres_web),
):
    return templates.TemplateResponse(
        request,
        "delegation/membre_form.html",
        {"user": user, "delegation": user.delegation, "item": None, "active": "membres"},
    )


@router.post("/delegation/membres/new")
def delegation_membres_create(
    full_name: str = Form(...),
    fonction: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_membres_web),
):
    membre = models.Membre(
        full_name=full_name,
        poste=fonction or None,
        phone=phone or None,
        email=email or None,
        delegation_id=user.delegation_id,
    )
    db.add(membre)
    db.commit()
    return RedirectResponse(url="/delegation/membres", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/delegation/membres/{membre_id}/delete")
def delegation_membres_delete(
    membre_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_membres_web),
):
    membre = db.get(models.Membre, membre_id)
    if membre and membre.delegation_id == user.delegation_id:
        db.delete(membre)
        db.commit()
    return RedirectResponse(url="/delegation/membres", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Cotisations de la délégation (lecture seule) ----------

@router.get("/delegation/cotisations")
def delegation_cotisations(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_cotisations_web),
):
    etablissements = (
        db.query(models.Etablissement)
        .filter(models.Etablissement.delegation_id == user.delegation_id)
        .order_by(models.Etablissement.nom)
        .all()
    )
    from ..reports import current_annee_scolaire

    annee = current_annee_scolaire()
    cotisations_by_etab = {
        c.etablissement_id: c
        for c in db.query(models.Cotisation).filter(
            models.Cotisation.etablissement_id.in_([e.id for e in etablissements]),
            models.Cotisation.annee_scolaire == annee,
        )
    }
    rows = []
    for e in etablissements:
        cotisation = cotisations_by_etab.get(e.id)
        rule = cotisation_rule(e.statut)
        rows.append(
            {
                "etablissement": e,
                "montant_du": cotisation.montant_du if cotisation else rule["montant_du"],
                "montant_paye": cotisation.montant_paye if cotisation else 0,
                "statut": cotisation.statut_paiement if cotisation else "impaye",
            }
        )
    return templates.TemplateResponse(
        request,
        "delegation/cotisations.html",
        {"user": user, "delegation": user.delegation, "rows": rows, "annee": annee, "active": "cotisations"},
    )


# ---------- Annonces ciblées vers les établissements de la délégation ----------

@router.get("/delegation/annonces")
def delegation_annonces_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_annonces_web),
):
    items = (
        db.query(models.AnnonceDelegation)
        .filter(models.AnnonceDelegation.delegation_id == user.delegation_id)
        .order_by(models.AnnonceDelegation.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "delegation/annonces_list.html",
        {"user": user, "delegation": user.delegation, "items": items, "active": "annonces"},
    )


@router.post("/delegation/annonces/new")
def delegation_annonces_create(
    titre: str = Form(...),
    message: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_annonces_web),
):
    annonce = models.AnnonceDelegation(
        delegation_id=user.delegation_id,
        titre=titre,
        message=message,
        created_by_id=user.id,
    )
    db.add(annonce)
    db.commit()
    return RedirectResponse(url="/delegation/annonces", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/delegation/annonces/{annonce_id}/delete")
def delegation_annonces_delete(
    annonce_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_annonces_web),
):
    annonce = db.get(models.AnnonceDelegation, annonce_id)
    if annonce and annonce.delegation_id == user.delegation_id:
        db.delete(annonce)
        db.commit()
    return RedirectResponse(url="/delegation/annonces", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Établissements de la région (lecture seule) ----------

@router.get("/delegation/etablissements")
def delegation_etablissements_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_etablissements_web),
):
    items = (
        db.query(models.Etablissement)
        .filter(models.Etablissement.delegation_id == user.delegation_id)
        .order_by(models.Etablissement.nom)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "delegation/etablissements_list.html",
        {"user": user, "delegation": user.delegation, "items": items, "active": "etablissements"},
    )


@router.get("/delegation/etablissements/{etablissement_id}")
def delegation_etablissement_detail(
    etablissement_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_etablissements_web),
):
    etablissement = db.get(models.Etablissement, etablissement_id)
    if not etablissement or etablissement.delegation_id != user.delegation_id:
        return RedirectResponse(url="/delegation/etablissements", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request,
        "delegation/etablissement_detail.html",
        {"user": user, "delegation": user.delegation, "etablissement": etablissement, "active": "etablissements"},
    )


# ---------- Rapport d'activité de la délégation (PDF, en libre-service) ----------

@router.get("/delegation/rapport.pdf")
def delegation_rapport_pdf(
    annee_scolaire: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_rapport_web),
):
    from ..reports import current_annee_scolaire, generate_delegation_report_pdf

    delegation = user.delegation
    if not delegation:
        return RedirectResponse(url="/delegation", status_code=status.HTTP_303_SEE_OTHER)
    annee = annee_scolaire or current_annee_scolaire()
    today = datetime.date.today()
    debut_annee = datetime.date(today.year if today.month >= 9 else today.year - 1, 9, 1)
    pdf_bytes = generate_delegation_report_pdf(db, delegation, annee, debut_annee, today, user)
    filename = safe_content_disposition(f"rapport-delegation-{delegation.nom}.pdf".replace(" ", "-"))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- Documents partagés de la délégation ----------

@router.get("/delegation/documents")
def delegation_documents_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_documents_web),
):
    items = (
        db.query(models.DocumentDelegation)
        .filter(models.DocumentDelegation.delegation_id == user.delegation_id)
        .order_by(models.DocumentDelegation.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "delegation/documents_list.html",
        {"user": user, "delegation": user.delegation, "items": items, "active": "documents", "error": None},
    )


@router.post("/delegation/documents/new")
async def delegation_documents_create(
    request: Request,
    title: str = Form(...),
    file: UploadFile = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_documents_web),
):
    try:
        stored_name, original_name = await storage.save_upload(
            db, file, DOCUMENTS_DELEGATION_DIR, storage.ALLOWED_DOCUMENT_EXT
        )
    except ValueError as exc:
        items = (
            db.query(models.DocumentDelegation)
            .filter(models.DocumentDelegation.delegation_id == user.delegation_id)
            .order_by(models.DocumentDelegation.created_at.desc())
            .all()
        )
        return templates.TemplateResponse(
            request,
            "delegation/documents_list.html",
            {"user": user, "delegation": user.delegation, "items": items, "active": "documents", "error": str(exc)},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    document = models.DocumentDelegation(
        delegation_id=user.delegation_id,
        title=title,
        file_path=f"{DOCUMENTS_DELEGATION_DIR}/{stored_name}",
        original_filename=original_name,
        uploaded_by_id=user.id,
    )
    db.add(document)
    db.commit()
    return RedirectResponse(url="/delegation/documents", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/delegation/documents/{document_id}/file")
def delegation_documents_file(
    document_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_documents_web),
):
    document = db.get(models.DocumentDelegation, document_id)
    if not document or document.delegation_id != user.delegation_id:
        return RedirectResponse(url="/delegation/documents", status_code=status.HTTP_303_SEE_OTHER)
    stored = storage.get_stored_file(db, document.file_path)
    if not stored:
        return RedirectResponse(url="/delegation/documents", status_code=status.HTTP_303_SEE_OTHER)
    return Response(
        content=stored.data,
        media_type=stored.content_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_content_disposition(document.original_filename)}"'},
    )


@router.post("/delegation/documents/{document_id}/delete")
def delegation_documents_delete(
    document_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_documents_web),
):
    document = db.get(models.DocumentDelegation, document_id)
    if document and document.delegation_id == user.delegation_id:
        storage.delete_stored_file(db, document.file_path)
        db.delete(document)
        db.commit()
    return RedirectResponse(url="/delegation/documents", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Messagerie avec le BEN national ----------

@router.get("/delegation/messagerie")
def delegation_messagerie_thread(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_messagerie_web),
):
    messages = (
        db.query(models.MessageDelegation)
        .filter(models.MessageDelegation.delegation_id == user.delegation_id)
        .order_by(models.MessageDelegation.created_at)
        .all()
    )
    unread = [m for m in messages if m.is_from_ben and not m.is_read_by_delegation]
    for m in unread:
        m.is_read_by_delegation = True
    if unread:
        db.commit()
    return templates.TemplateResponse(
        request,
        "delegation/messagerie.html",
        {"user": user, "delegation": user.delegation, "messages": messages, "active": "messagerie"},
    )


@router.post("/delegation/messagerie/new")
def delegation_messagerie_reply(
    body: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_delegation_messagerie_web),
):
    delegation = user.delegation
    message = models.MessageDelegation(
        delegation_id=user.delegation_id,
        sender_id=user.id,
        is_from_ben=False,
        body=body,
    )
    db.add(message)
    db.flush()
    if delegation:
        destinataires = [
            u for u in db.query(models.User).filter(models.User.delegation_id.is_(None), models.User.etablissement_id.is_(None))
            if u.can_manage_delegations
        ]
        for dest in destinataires:
            notify(db, dest.id, f"Nouveau message de la délégation {delegation.nom}.", link="/admin/messagerie-delegations")
    db.commit()
    return RedirectResponse(url="/delegation/messagerie", status_code=status.HTTP_303_SEE_OTHER)
