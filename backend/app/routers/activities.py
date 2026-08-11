from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_activities_editor

router = APIRouter(prefix="/api/activities", tags=["activities"])


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
