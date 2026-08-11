"""Journal d'audit : enregistre les actions sensibles (comptes, finances, cartes,
délégations, contenu du site). Appeler `log()` avant le `db.commit()` de la route
concernée — l'entrée d'audit est persistée dans la même transaction."""

from sqlalchemy.orm import Session

from . import models


def log(
    db: Session,
    user: "models.User | None",
    action: str,
    entity_type: str,
    entity_id,
    description: str,
) -> None:
    db.add(
        models.AuditLog(
            user_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            description=description,
        )
    )
