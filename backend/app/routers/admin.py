import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .. import audit, models
from ..attestations_pdf import generate_membre_attestation_pdf
from ..connexion_log import record_login
from ..database import get_db
from ..deps import (
    require_activities_access_web,
    require_admin_web,
    require_contact_access_web,
    require_login_web,
    require_news_access_web,
)
from ..security import create_access_token, hash_password, password_policy_error, verify_password
from .admin_files import ALLOWED_PHOTO_EXT, UPLOAD_ROOT, _save_upload

router = APIRouter(prefix="/admin", tags=["admin-panel"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

NEWS_IMAGES_DIR = UPLOAD_ROOT / "news"


# ---------- Auth ----------

@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "admin/login.html", {"error": None})


MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    portal: str = Form("ben"),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.email == email).first()

    if user and user.locked_until and user.locked_until > datetime.datetime.utcnow():
        minutes_left = max(1, int((user.locked_until - datetime.datetime.utcnow()).total_seconds() // 60) + 1)
        return templates.TemplateResponse(
            request,
            "admin/login.html",
            {"error": f"Compte temporairement verrouillé après plusieurs échecs. Réessayez dans {minutes_left} min."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if not user or not verify_password(password, user.hashed_password):
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
                user.locked_until = datetime.datetime.utcnow() + datetime.timedelta(minutes=LOCKOUT_MINUTES)
                user.failed_login_attempts = 0
            db.commit()
        return templates.TemplateResponse(
            request,
            "admin/login.html",
            {"error": "Identifiants incorrects."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user.failed_login_attempts = 0
    user.locked_until = None

    account_portal = (
        "delegation" if user.is_delegation_account
        else "etablissement" if user.is_etablissement_account
        else "ben"
    )
    if portal != account_portal:
        login_template = {
            "delegation": "delegation_login.html",
            "etablissement": "etablissement_login.html",
            "ben": "admin/login.html",
        }[account_portal]
        message = {
            "delegation": "Ce compte doit se connecter depuis l'espace délégations régionales.",
            "etablissement": "Ce compte doit se connecter depuis l'espace établissement.",
            "ben": "Ce compte n'a pas accès à cet espace.",
        }[account_portal]
        return templates.TemplateResponse(
            request,
            login_template,
            {"error": message},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    token = create_access_token(subject=user.email)
    redirect_url = {"delegation": "/delegation", "etablissement": "/etablissement", "ben": "/admin"}[account_portal]
    audit.log(db, user, "login", "Connexion", user.id, f"{user.full_name} s'est connecté ({account_portal})")
    record_login(db, user, request)
    db.commit()
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=60 * 60 * 6)
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response


@router.get("/mon-compte/mot-de-passe")
def change_password_page(
    request: Request,
    user: models.User = Depends(require_login_web),
):
    return templates.TemplateResponse(request, "admin/change_password.html", {"admin": user, "active": "mon_compte", "error": None, "success": None})


@router.post("/mon-compte/mot-de-passe")
def change_password_submit(
    request: Request,
    mot_de_passe_actuel: str = Form(...),
    nouveau_mot_de_passe: str = Form(...),
    confirmation: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_web),
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
            "admin/change_password.html",
            {"admin": user, "active": "mon_compte", "error": error, "success": None},
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
        "admin/change_password.html",
        {"admin": user, "active": "mon_compte", "error": None, "success": "Mot de passe mis à jour."},
    )


@router.get("/attestation/pdf")
def attestation_membre_pdf(
    user: models.User = Depends(require_login_web),
):
    pdf_bytes = generate_membre_attestation_pdf(user)
    filename = f"attestation_appartenance_{user.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- Dashboard ----------

@router.get("")
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_web),
):
    counts = {}
    if user.can_manage_reunions:
        counts["reunions"] = db.query(models.Reunion).count()
    if user.can_manage_membres:
        counts["membres"] = db.query(models.Membre).count()
    if user.can_manage_documents:
        counts["documents"] = db.query(models.Document).count()
    if user.can_manage_photos:
        counts["photos"] = db.query(models.Photo).count()
    if user.can_manage_news:
        counts["news"] = db.query(models.NewsPost).count()
    if user.can_manage_activities:
        counts["activities"] = db.query(models.Activity).count()
    if user.can_manage_contact:
        counts["messages"] = db.query(models.ContactMessage).count()
        counts["unread_messages"] = (
            db.query(models.ContactMessage).filter(models.ContactMessage.is_read.is_(False)).count()
        )
        counts["unread_adhesion_requests"] = (
            db.query(models.AdhesionRequest).filter(models.AdhesionRequest.is_read.is_(False)).count()
        )
    if user.is_admin:
        counts["users"] = db.query(models.User).count()

    has_any_module = bool(counts) or user.can_manage_finances

    unread_notifications = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user.id, models.Notification.is_read.is_(False))
        .order_by(models.Notification.created_at.desc())
        .all()
    )

    ma_carte = (
        db.query(models.CarteMembre)
        .filter(models.CarteMembre.user_id == user.id)
        .order_by(models.CarteMembre.date_soumission.desc())
        .first()
    )

    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {
            "admin": user,
            "counts": counts,
            "has_any_module": has_any_module,
            "unread_notifications": unread_notifications,
            "ma_carte": ma_carte,
            "active": "dashboard",
        },
    )


# ---------- News ----------

@router.get("/news")
def news_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_news_access_web),
):
    items = db.query(models.NewsPost).order_by(desc(models.NewsPost.published_at)).all()
    return templates.TemplateResponse(
        request,
        "admin/news_list.html",
        {"admin": user, "items": items, "active": "news"},
    )


@router.get("/news/new")
def news_new_form(
    request: Request,
    user: models.User = Depends(require_news_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/news_form.html",
        {
            "admin": user,
            "item": None,
            "today": datetime.date.today(),
            "active": "news",
        },
    )


@router.post("/news/new")
async def news_create(
    request: Request,
    title: str = Form(...),
    excerpt: str = Form(...),
    content: str = Form(""),
    published_at: datetime.date = Form(...),
    is_published: bool = Form(False),
    image: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_news_access_web),
):
    if len(title.strip()) < 3 or len(excerpt.strip()) < 3:
        return templates.TemplateResponse(
            request,
            "admin/news_form.html",
            {
                "admin": user,
                "item": None,
                "today": datetime.date.today(),
                "active": "news",
                "error": "Le titre et le résumé doivent contenir au moins 3 caractères.",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    image_path = None
    if image is not None and image.filename:
        try:
            stored_name, _ = await _save_upload(image, NEWS_IMAGES_DIR, ALLOWED_PHOTO_EXT)
            image_path = f"news/{stored_name}"
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "admin/news_form.html",
                {
                    "admin": user,
                    "item": None,
                    "today": datetime.date.today(),
                    "active": "news",
                    "error": str(exc),
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    news = models.NewsPost(
        title=title,
        excerpt=excerpt,
        content=content,
        published_at=published_at,
        is_published=is_published,
        image_path=image_path,
    )
    db.add(news)
    db.commit()
    return RedirectResponse(url="/admin/news", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/news/{news_id}/edit")
def news_edit_form(
    news_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_news_access_web),
):
    item = db.get(models.NewsPost, news_id)
    return templates.TemplateResponse(
        request,
        "admin/news_form.html",
        {"admin": user, "item": item, "active": "news"},
    )


@router.post("/news/{news_id}/edit")
async def news_update(
    news_id: int,
    request: Request,
    title: str = Form(...),
    excerpt: str = Form(...),
    content: str = Form(""),
    published_at: datetime.date = Form(...),
    is_published: bool = Form(False),
    image: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_news_access_web),
):
    news = db.get(models.NewsPost, news_id)
    if news and (len(title.strip()) < 3 or len(excerpt.strip()) < 3):
        return templates.TemplateResponse(
            request,
            "admin/news_form.html",
            {
                "admin": user,
                "item": news,
                "active": "news",
                "error": "Le titre et le résumé doivent contenir au moins 3 caractères.",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if news:
        if image is not None and image.filename:
            try:
                stored_name, _ = await _save_upload(image, NEWS_IMAGES_DIR, ALLOWED_PHOTO_EXT)
            except ValueError as exc:
                return templates.TemplateResponse(
                    request,
                    "admin/news_form.html",
                    {"admin": user, "item": news, "active": "news", "error": str(exc)},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            old_path = UPLOAD_ROOT / news.image_path if news.image_path else None
            news.image_path = f"news/{stored_name}"
            if old_path and old_path.exists():
                old_path.unlink()

        news.title = title
        news.excerpt = excerpt
        news.content = content
        news.published_at = published_at
        news.is_published = is_published
        db.commit()
    return RedirectResponse(url="/admin/news", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/news/{news_id}/delete")
def news_delete(
    news_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_news_access_web),
):
    news = db.get(models.NewsPost, news_id)
    if news:
        old_path = UPLOAD_ROOT / news.image_path if news.image_path else None
        db.delete(news)
        db.commit()
        if old_path and old_path.exists():
            old_path.unlink()
    return RedirectResponse(url="/admin/news", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Activities ----------

@router.get("/activities")
def activities_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_activities_access_web),
):
    items = db.query(models.Activity).order_by(models.Activity.event_date).all()
    return templates.TemplateResponse(
        request,
        "admin/activities_list.html",
        {"admin": user, "items": items, "active": "activities"},
    )


@router.get("/activities/new")
def activities_new_form(
    request: Request,
    user: models.User = Depends(require_activities_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/activities_form.html",
        {"admin": user, "item": None, "active": "activities"},
    )


@router.post("/activities/new")
def activities_create(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    event_date: datetime.date = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_activities_access_web),
):
    if len(title.strip()) < 3 or len(description.strip()) < 3:
        return templates.TemplateResponse(
            request,
            "admin/activities_form.html",
            {
                "admin": user,
                "item": None,
                "active": "activities",
                "error": "Le titre et la description doivent contenir au moins 3 caractères.",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    activity = models.Activity(title=title, description=description, event_date=event_date)
    db.add(activity)
    db.commit()
    return RedirectResponse(url="/admin/activities", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/activities/{activity_id}/edit")
def activities_edit_form(
    activity_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_activities_access_web),
):
    item = db.get(models.Activity, activity_id)
    return templates.TemplateResponse(
        request,
        "admin/activities_form.html",
        {"admin": user, "item": item, "active": "activities"},
    )


@router.post("/activities/{activity_id}/edit")
def activities_update(
    activity_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    event_date: datetime.date = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_activities_access_web),
):
    activity = db.get(models.Activity, activity_id)
    if activity and (len(title.strip()) < 3 or len(description.strip()) < 3):
        activity.title = title
        activity.description = description
        activity.event_date = event_date
        return templates.TemplateResponse(
            request,
            "admin/activities_form.html",
            {
                "admin": user,
                "item": activity,
                "active": "activities",
                "error": "Le titre et la description doivent contenir au moins 3 caractères.",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if activity:
        activity.title = title
        activity.description = description
        activity.event_date = event_date
        db.commit()
    return RedirectResponse(url="/admin/activities", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/activities/{activity_id}/delete")
def activities_delete(
    activity_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_activities_access_web),
):
    activity = db.get(models.Activity, activity_id)
    if activity:
        db.delete(activity)
        db.commit()
    return RedirectResponse(url="/admin/activities", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Messages ----------

@router.get("/messages")
def messages_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_contact_access_web),
):
    items = db.query(models.ContactMessage).order_by(desc(models.ContactMessage.created_at)).all()
    return templates.TemplateResponse(
        request,
        "admin/messages_list.html",
        {"admin": user, "items": items, "active": "messages"},
    )


@router.post("/messages/{message_id}/read")
def message_mark_read(
    message_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_contact_access_web),
):
    message = db.get(models.ContactMessage, message_id)
    if message:
        message.is_read = True
        db.commit()
    return RedirectResponse(url="/admin/messages", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/messages/{message_id}/delete")
def message_delete(
    message_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_contact_access_web),
):
    message = db.get(models.ContactMessage, message_id)
    if message:
        db.delete(message)
        db.commit()
    return RedirectResponse(url="/admin/messages", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Demandes d'adhésion ----------

@router.get("/adhesion-requests")
def adhesion_requests_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_contact_access_web),
):
    items = db.query(models.AdhesionRequest).order_by(desc(models.AdhesionRequest.created_at)).all()
    return templates.TemplateResponse(
        request,
        "admin/adhesion_requests_list.html",
        {"admin": user, "items": items, "active": "adhesion_requests"},
    )


@router.post("/adhesion-requests/{request_id}/read")
def adhesion_request_mark_read(
    request_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_contact_access_web),
):
    item = db.get(models.AdhesionRequest, request_id)
    if item:
        item.is_read = True
        db.commit()
    return RedirectResponse(url="/admin/adhesion-requests", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/adhesion-requests/{request_id}/delete")
def adhesion_request_delete(
    request_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_contact_access_web),
):
    item = db.get(models.AdhesionRequest, request_id)
    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse(url="/admin/adhesion-requests", status_code=status.HTTP_303_SEE_OTHER)
