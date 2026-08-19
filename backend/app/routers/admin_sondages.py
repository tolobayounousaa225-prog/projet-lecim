import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import audit, models
from ..database import get_db
from ..deps import require_login_web, require_sondages_access_web

router = APIRouter(prefix="/admin/sondages", tags=["admin-sondages"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


# ---------- Espace de vote (tout compte BEN connecté) ----------

@router.get("")
def sondages_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_web),
):
    items = db.query(models.Sondage).order_by(models.Sondage.created_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin/sondages_list.html",
        {"admin": user, "items": items, "active": "sondages"},
    )


@router.get("/{sondage_id}")
def sondage_detail(
    sondage_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_web),
):
    sondage = db.get(models.Sondage, sondage_id)
    if not sondage:
        return RedirectResponse(url="/admin/sondages", status_code=status.HTTP_303_SEE_OTHER)
    a_vote = sondage.a_vote(user.id)
    show_results = a_vote or not sondage.is_ouvert
    return templates.TemplateResponse(
        request,
        "admin/sondage_detail.html",
        {
            "admin": user,
            "sondage": sondage,
            "a_vote": a_vote,
            "show_results": show_results,
            "total_votes": len(sondage.votes),
            "active": "sondages",
        },
    )


@router.post("/{sondage_id}/voter")
def sondage_voter(
    sondage_id: int,
    option_id: int = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_web),
):
    sondage = db.get(models.Sondage, sondage_id)
    if not sondage or not sondage.is_ouvert or sondage.a_vote(user.id):
        return RedirectResponse(url=f"/admin/sondages/{sondage_id}", status_code=status.HTTP_303_SEE_OTHER)
    option = db.get(models.SondageOption, option_id)
    if not option or option.sondage_id != sondage_id:
        return RedirectResponse(url=f"/admin/sondages/{sondage_id}", status_code=status.HTTP_303_SEE_OTHER)

    db.add(models.SondageVote(sondage_id=sondage_id, option_id=option_id, user_id=user.id))
    audit.log(db, user, "create", "Vote", sondage_id, f"A voté au sondage « {sondage.titre} »")
    try:
        db.commit()
    except IntegrityError:
        # Double-clic/double requête concurrente : la contrainte uq_sondage_vote_user
        # a bloqué un second vote — ce n'est pas une erreur, juste un vote déjà pris
        # en compte par l'autre requête.
        db.rollback()
    return RedirectResponse(url=f"/admin/sondages/{sondage_id}", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Gestion des sondages (module dédié) ----------

@router.get("/gestion/liste")
def sondages_gestion_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_sondages_access_web),
):
    items = db.query(models.Sondage).order_by(models.Sondage.created_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin/sondages_gestion_list.html",
        {"admin": user, "items": items, "active": "sondages_gestion"},
    )


@router.get("/gestion/new")
def sondage_new_form(
    request: Request,
    user: models.User = Depends(require_sondages_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/sondage_form.html",
        {"admin": user, "active": "sondages_gestion"},
    )


@router.post("/gestion/new")
async def sondage_create(
    request: Request,
    titre: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_sondages_access_web),
):
    form = await request.form()
    options_text = [v.strip() for k, v in form.multi_items() if k == "options" and v.strip()]
    if len(options_text) < 2:
        return templates.TemplateResponse(
            request,
            "admin/sondage_form.html",
            {"admin": user, "active": "sondages_gestion", "error": "Veuillez saisir au moins deux options.", "titre": titre, "description": description},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    sondage = models.Sondage(titre=titre, description=description or None, created_by_id=user.id)
    db.add(sondage)
    db.flush()
    for i, texte in enumerate(options_text):
        db.add(models.SondageOption(sondage_id=sondage.id, texte=texte, ordre=i))
    audit.log(db, user, "create", "Sondage", sondage.id, f"A créé le sondage « {sondage.titre} »")
    db.commit()
    return RedirectResponse(url="/admin/sondages/gestion/liste", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/gestion/{sondage_id}")
def sondage_gestion_detail(
    sondage_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_sondages_access_web),
):
    sondage = db.get(models.Sondage, sondage_id)
    if not sondage:
        return RedirectResponse(url="/admin/sondages/gestion/liste", status_code=status.HTTP_303_SEE_OTHER)
    votes = sorted(sondage.votes, key=lambda v: v.created_at, reverse=True)
    return templates.TemplateResponse(
        request,
        "admin/sondage_gestion_detail.html",
        {"admin": user, "sondage": sondage, "votes": votes, "total_votes": len(sondage.votes), "active": "sondages_gestion"},
    )


@router.post("/gestion/{sondage_id}/cloturer")
def sondage_cloturer(
    sondage_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_sondages_access_web),
):
    sondage = db.get(models.Sondage, sondage_id)
    if sondage and sondage.is_ouvert:
        sondage.is_ouvert = False
        sondage.cloture_at = datetime.datetime.utcnow()
        audit.log(db, user, "update", "Sondage", sondage.id, f"A clôturé le sondage « {sondage.titre} »")
        db.commit()
    return RedirectResponse(url=f"/admin/sondages/gestion/{sondage_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/gestion/{sondage_id}/reouvrir")
def sondage_reouvrir(
    sondage_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_sondages_access_web),
):
    sondage = db.get(models.Sondage, sondage_id)
    if sondage and not sondage.is_ouvert:
        sondage.is_ouvert = True
        sondage.cloture_at = None
        audit.log(db, user, "update", "Sondage", sondage.id, f"A rouvert le sondage « {sondage.titre} »")
        db.commit()
    return RedirectResponse(url=f"/admin/sondages/gestion/{sondage_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/gestion/{sondage_id}/delete")
def sondage_delete(
    sondage_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_sondages_access_web),
):
    sondage = db.get(models.Sondage, sondage_id)
    if sondage:
        audit.log(db, user, "delete", "Sondage", sondage.id, f"A supprimé le sondage « {sondage.titre} »")
        db.delete(sondage)
        db.commit()
    return RedirectResponse(url="/admin/sondages/gestion/liste", status_code=status.HTTP_303_SEE_OTHER)
