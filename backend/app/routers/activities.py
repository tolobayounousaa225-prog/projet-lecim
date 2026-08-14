import datetime
import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_activities_editor

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


@router.get("/{activity_id}", response_model=schemas.ActivityOut)
def get_activity(activity_id: int, db: Session = Depends(get_db)):
    activity = db.get(models.Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activité introuvable")
    return activity


@router.get("/{activity_id}/ics")
def activity_ics(activity_id: int, db: Session = Depends(get_db)):
    """Fichier .ics téléchargeable pour ajouter l'événement à un calendrier personnel
    (Google Calendar, Outlook, Apple Calendar, etc.) — public, comme la liste elle-même."""
    activity = db.get(models.Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activité introuvable")

    dtstart = activity.event_date.strftime("%Y%m%d")
    dtstamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//LECIM//Evenements//FR\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:lecim-activity-{activity.id}@lecim\r\n"
        f"DTSTAMP:{dtstamp}\r\n"
        f"DTSTART;VALUE=DATE:{dtstart}\r\n"
        f"SUMMARY:{_ics_escape(activity.title)}\r\n"
        f"DESCRIPTION:{_ics_escape(activity.description)}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
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
