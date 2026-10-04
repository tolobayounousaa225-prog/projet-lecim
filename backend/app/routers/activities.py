import datetime
import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_activities_editor
from ..rate_limit import rate_limiter

router = APIRouter(prefix="/api/activities", tags=["activities"])


def _ics_escape(text: str) -> str:
    return re.sub(r"([,;\\])", r"\\\1", text).replace("\n", "\\n")


@router.get("", response_model=list[schemas.ActivityOut])
def list_activities(db: Session = Depends(get_db)):
    return (
        db.query(models.Activity)
        .order_by(models.Activity.event_date)
        .all()
    )


def _activity_vevent(activity: models.Activity, dtstamp: str) -> str:
    dtstart = activity.event_date.strftime("%Y%m%d")
    return (
        "BEGIN:VEVENT\r\n"
        f"UID:lecim-activity-{activity.id}@lecim\r\n"
        f"DTSTAMP:{dtstamp}\r\n"
        f"DTSTART;VALUE=DATE:{dtstart}\r\n"
        f"SUMMARY:{_ics_escape(activity.title)}\r\n"
        f"DESCRIPTION:{_ics_escape(activity.description)}\r\n"
        "END:VEVENT\r\n"
    )


@router.get("/calendar.ics")
def activities_calendar_ics(db: Session = Depends(get_db)):
    """Calendrier combine de toutes les activites, abonnable (URL stable) dans un
    calendrier personnel (Google Calendar "A partir d'une URL", Outlook, Apple Calendar)
    plutot que telecharge evenement par evenement comme /{id}/ics ci-dessous. Doit rester
    enregistree avant /{activity_id} pour ne pas etre interceptee par ce chemin generique."""
    activities = db.query(models.Activity).order_by(models.Activity.event_date).all()
    dtstamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    body = "".join(_activity_vevent(a, dtstamp) for a in activities)
    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//LECIM//Evenements//FR\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:PUBLISH\r\n"
        "X-WR-CALNAME:LECIM - Activites\r\n"
        + body
        + "END:VCALENDAR\r\n"
    )
    return Response(
        content=ics,
        media_type="text/calendar",
        headers={"Content-Disposition": 'inline; filename="lecim-calendrier.ics"'},
    )


@router.get("/{activity_id}", response_model=schemas.ActivityOut)
def get_activity(activity_id: int, db: Session = Depends(get_db)):
    activity = db.get(models.Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activité introuvable")
    return activity


@router.post(
    "/{activity_id}/inscriptions",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limiter("activity-inscription", 10, 60))],
)
def create_inscription(
    activity_id: int,
    payload: schemas.ActivityInscriptionCreate,
    db: Session = Depends(get_db),
):
    activity = db.get(models.Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activité introuvable")
    if activity.status != "upcoming":
        raise HTTPException(status_code=400, detail="Cette activité est déjà terminée")
    db.add(models.ActivityInscription(activity_id=activity_id, **payload.model_dump()))
    db.commit()
    return {"ok": True}


@router.get("/{activity_id}/ics")
def activity_ics(activity_id: int, db: Session = Depends(get_db)):
    """Fichier .ics téléchargeable pour ajouter l'événement à un calendrier personnel
    (Google Calendar, Outlook, Apple Calendar, etc.) — public, comme la liste elle-même."""
    activity = db.get(models.Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activité introuvable")

    dtstamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//LECIM//Evenements//FR\r\n"
        "CALSCALE:GREGORIAN\r\n"
        + _activity_vevent(activity, dtstamp)
        + "END:VCALENDAR\r\n"
    )
    return Response(
        content=ics,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="lecim-evenement-{activity.id}.ics"'},
    )


@router.post("", response_model=schemas.ActivityOut, status_code=status.HTTP_201_CREATED)
def create_activity(
    payload: schemas.ActivityCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_activities_editor),
):
    activity = models.Activity(**payload.model_dump())
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


@router.put("/{activity_id}", response_model=schemas.ActivityOut)
def update_activity(
    activity_id: int,
    payload: schemas.ActivityUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_activities_editor),
):
    activity = db.get(models.Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activité introuvable")
    for field, value in payload.model_dump().items():
        setattr(activity, field, value)
    db.commit()
    db.refresh(activity)
    return activity


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_activities_editor),
):
    activity = db.get(models.Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activité introuvable")
    db.delete(activity)
    db.commit()
