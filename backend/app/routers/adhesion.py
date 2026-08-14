from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/adhesion-requests", tags=["adhesion"])


@router.post("", response_model=schemas.AdhesionRequestOut, status_code=status.HTTP_201_CREATED)
def submit_adhesion_request(payload: schemas.AdhesionRequestCreate, db: Session = Depends(get_db)):
    request = models.AdhesionRequest(**payload.model_dump())
    db.add(request)
    db.commit()
    db.refresh(request)
    return request
