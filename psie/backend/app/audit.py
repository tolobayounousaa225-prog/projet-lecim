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
    """Ajoute une entrée au journal d'audit (au caller de committer). En mode consultation (supervision), l'action est
    attribuée à la personne qui consulte, jamais au compte consulté."""
    real = getattr(user, "_real", None)
    if real is not None:
        detail = f"[consultation de {user.email}] {detail or ''}".strip()
        user = real
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


# ---------------------------------------------------------------- Consultation du journal

import csv
import datetime
import io

# Actions qui méritent un coup d'œil de l'administrateur : droits, comptes, suppressions, signatures, décisions.
SENSITIVE_ACTIONS = {
    "suppression", "reinitialisation_mdp", "desactivation", "acces_roles", "acces_personne", "acces_reinitialisation",
    "signature", "decision", "import", "recensement_supprime", "consultation_compte",
}
SENSITIVE_ENTITIES_ON_CREATE = {"user"}          # la création d'un compte est toujours signalée
PAGE_SIZE = 100


def is_sensitive(entry: "models.AuditLog") -> bool:
    return entry.action in SENSITIVE_ACTIONS or (entry.action == "creation" and entry.entity in SENSITIVE_ENTITIES_ON_CREATE)


def filter_query(db: Session, q: str = "", action: str = "", entity: str = "", user: str = "", start: str = "",
                 end: str = "", only_sensitive: bool = False):
    query = db.query(models.AuditLog)
    if action:
        query = query.filter(models.AuditLog.action == action)
    if entity:
        query = query.filter(models.AuditLog.entity == entity)
    if user.strip():
        query = query.filter(models.AuditLog.user_email.ilike(f"%{user.strip()[:80]}%"))
    if q.strip():
        like = f"%{q.strip()[:80]}%"
        query = query.filter(models.AuditLog.detail.ilike(like) | models.AuditLog.entity.ilike(like) | models.AuditLog.action.ilike(like))
    try:
        if start:
            query = query.filter(models.AuditLog.created_at >= datetime.datetime.combine(datetime.date.fromisoformat(start), datetime.time.min))
        if end:
            query = query.filter(models.AuditLog.created_at <= datetime.datetime.combine(datetime.date.fromisoformat(end), datetime.time.max))
    except ValueError:
        pass                                     # date mal saisie : le filtre est ignoré
    if only_sensitive:
        query = query.filter(models.AuditLog.action.in_(SENSITIVE_ACTIONS)
                             | ((models.AuditLog.action == "creation") & models.AuditLog.entity.in_(SENSITIVE_ENTITIES_ON_CREATE)))
    return query.order_by(models.AuditLog.id.desc())


def distinct_values(db: Session) -> tuple[list[str], list[str]]:
    actions = sorted(a for (a,) in db.query(models.AuditLog.action).distinct())
    entities = sorted(e for (e,) in db.query(models.AuditLog.entity).distinct())
    return actions, entities


def _safe(value: str | None) -> str:
    v = value or ""
    return "'" + v if v[:1] in ("=", "+", "-", "@") else v        # neutralise les formules Excel


def to_csv(entries) -> str:
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow(["Date", "Personne", "Action", "Objet", "N°", "Détail", "Sensible"])
    for a in entries:
        w.writerow([a.created_at.strftime("%Y-%m-%d %H:%M:%S"), _safe(a.user_email), _safe(a.action), _safe(a.entity),
                    a.entity_id or "", _safe(a.detail), "oui" if is_sensitive(a) else ""])
    return "﻿" + out.getvalue()
