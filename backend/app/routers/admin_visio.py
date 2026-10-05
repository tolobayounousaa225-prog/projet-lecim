from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette import status

from .. import models
from ..config import settings
from ..database import get_db
from ..deps import require_reunions_access_web
from ..jitsi import generate_jitsi_token, jitsi_room_name
from ..reminders import send_visio_invitation

router = APIRouter(prefix="/admin", tags=["admin-visio"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/reunions/{reunion_id}/visio")
def reunion_visio(
    reunion_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    """Salle de visioconférence liée à une réunion — accès réservé aux comptes BEN
    ayant le module réunions (même périmètre que la fiche de la réunion elle-même).
    Le jeton Jitsi n'est valable que pour ce salon précis et expire après quelques
    heures : impossible d'utiliser le lien pour rejoindre un autre salon ou plus tard."""
    reunion = db.get(models.Reunion, reunion_id)
    if not reunion:
        return RedirectResponse(url="/admin/reunions", status_code=status.HTTP_303_SEE_OTHER)

    room = jitsi_room_name(reunion.id)
    moderator = user.is_admin or reunion.created_by_id == user.id
    token = generate_jitsi_token(room, user.full_name, user.email, moderator=moderator)

    return templates.TemplateResponse(
        request,
        "admin/reunion_visio.html",
        {
            "reunion": reunion,
            "jitsi_domain": settings.jitsi_domain,
            "jitsi_room": room,
            "jitsi_token": token,
        },
    )


@router.post("/reunions/{reunion_id}/visio/inviter")
def reunion_visio_inviter(
    reunion_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_reunions_access_web),
):
    """Action explicite, distincte de l'ouverture de l'appel : prévient tous les
    membres concernés (notification interne + e-mail) qu'un appel est en cours et
    qu'ils peuvent le rejoindre maintenant. Volontairement séparée de la simple
    ouverture de /visio pour ne pas re-notifier tout le monde à chaque fois qu'un
    participant rouvre ou rejoint le même appel."""
    reunion = db.get(models.Reunion, reunion_id)
    if reunion:
        send_visio_invitation(db, reunion, user)
    return RedirectResponse(url=f"/admin/reunions/{reunion_id}", status_code=status.HTTP_303_SEE_OTHER)
