import smtplib
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..database import get_db
from ..deps import get_current_admin

router = APIRouter(prefix="/api/contact", tags=["contact"])


def _notify_by_email(message: models.ContactMessage) -> None:
    if not settings.smtp_host or not settings.contact_notify_email:
        return
    try:
        email = EmailMessage()
        email["Subject"] = f"[LECIM] Nouveau message : {message.subject}"
        email["From"] = settings.smtp_from
        email["To"] = settings.contact_notify_email
        email.set_content(
            f"Nom: {message.full_name}\n"
            f"Email: {message.email}\n"
            f"Téléphone: {message.phone or '-'}\n"
            f"Établissement: {message.establishment or '-'}\n\n"
            f"{message.message}"
        )
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(email)
    except Exception:
        # La notification par e-mail ne doit jamais faire échouer la soumission du formulaire
        pass


@router.post("", response_model=schemas.ContactOut, status_code=status.HTTP_201_CREATED)
def submit_contact(payload: schemas.ContactCreate, db: Session = Depends(get_db)):
    message = models.ContactMessage(**payload.model_dump())
    db.add(message)
    db.commit()
    db.refresh(message)
    _notify_by_email(message)
    return message


@router.get("", response_model=list[schemas.ContactOut])
def list_contact_messages(
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    return db.query(models.ContactMessage).order_by(desc(models.ContactMessage.created_at)).all()


@router.patch("/{message_id}/read", response_model=schemas.ContactOut)
def mark_as_read(
    message_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    message = db.get(models.ContactMessage, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message introuvable")
    message.is_read = True
    db.commit()
    db.refresh(message)
    return message


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(
    message_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    message = db.get(models.ContactMessage, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message introuvable")
    db.delete(message)
    db.commit()
