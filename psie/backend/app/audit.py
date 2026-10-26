from sqlalchemy.orm import Session

from . import models


def log_action(
    db: Session,
    user: "models.User | None",
    action: str,
    entity: str,
    entity_id: int | None = None,
    detail: str | None = None,
) -> None:
    """Ajoute une entrée au journal d'audit (au caller de committer)."""
    db.add(
        models.AuditLog(
            user_id=user.id if user else None,
            user_email=user.email if user else None,
            action=action,
            entity=entity,
            entity_id=entity_id,
            detail=detail,
        )
    )
