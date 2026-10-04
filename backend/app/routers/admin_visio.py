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
    token = generate_jitsi_token(room, user.full_name, user.email, moderator=True)

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
