"""Rappels réglementaires (cahier des charges, 4.5) : mandats qui arrivent à échéance, rapport semestriel de la
DEN au CA (Statuts art. 18), états financiers à mettre à disposition 15 jours avant l'AG (art. 36).
Chaque rappel n'est envoyé qu'une fois (RappelLog)."""

import datetime

from sqlalchemy.orm import Session

from . import models
from .emailing import send_email

MANDAT_SEUILS = (90, 30, 7, 0)          # jours avant la fin d'un mandat
MANDAT_OUBLI_JOURS = 30                 # un mandat expiré depuis plus longtemps n'est plus signalé
RAPPORT_AVANT_FIN_SEMESTRE_JOURS = 15
DEMANDE_A_EXAMINER_JOURS = 7            # demande d'adhésion restée sans examen
DEMANDE_AVIS_CA_JOURS = 15              # demande dont l'avis écrit du CA se fait attendre


def _emails(db: Session, roles: set[str]) -> list[str]:
    return sorted({u.email for u in db.query(models.User).filter(models.User.is_active.is_(True)) if u.role in roles})


def _claim(db: Session, key: str) -> bool:
    """Réserve un rappel : False s'il a déjà été envoyé."""
    if db.query(models.RappelLog).filter_by(cle=key).first():
        return False
    db.add(models.RappelLog(cle=key))
    db.flush()
    return True


def _send_all(recipients: list[str], subject: str, body: str, sender) -> int:
    return sum(1 for to in recipients if sender(to, subject, body))


def mandats_a_echeance(db: Session, today: datetime.date, sender) -> int:
    lines = []
    for m in db.query(models.Mandat).filter(models.Mandat.date_fin.is_not(None)):
        days = (m.date_fin - today).days
        if days < -MANDAT_OUBLI_JOURS:
            continue
        seuil = min((s for s in MANDAT_SEUILS if days <= s), default=None)
        if seuil is None or not _claim(db, f"mandat:{m.id}:{seuil}"):
            continue
        qui = f" ({m.faitiere.sigle})" if m.faitiere else ""
        statut = "expiré" if days < 0 else ("expire aujourd'hui" if days == 0 else f"expire dans {days} jour(s)")
        lines.append(f"- {m.full_name}{qui}, {models.ORGANES.get(m.organe, m.organe)} : mandat {statut} (fin le {m.date_fin:%d/%m/%Y})")
    if not lines:
        return 0
    recipients = _emails(db, {"den", "secretaire"})
    body = ("Mandats à renouveler ou à clôturer (durée statutaire de 3 ans) :\n\n" + "\n".join(lines) +
            "\n\nPensez aussi à déclarer à l'autorité les changements d'organes (Règlement Intérieur, art. 39).\n")
    return _send_all(recipients, "PSIE — Mandats arrivant à échéance", body, sender)


def rapport_semestriel(db: Session, today: datetime.date, sender) -> int:
    """Rappel au DEN : rapport semestriel au CA, dans les 15 derniers jours de chaque semestre."""
    for semestre, fin in ((1, datetime.date(today.year, 6, 30)), (2, datetime.date(today.year, 12, 31))):
        days = (fin - today).days
        if 0 <= days <= RAPPORT_AVANT_FIN_SEMESTRE_JOURS and _claim(db, f"rapport-semestriel:{today.year}-{semestre}"):
            body = (f"Le semestre {semestre} {today.year} se termine le {fin:%d/%m/%Y}. La Direction Exécutive Nationale doit "
                    "présenter son rapport semestriel au Conseil d'Administration (Statuts, art. 18).\n")
            return _send_all(_emails(db, {"den"}), f"PSIE — Rapport semestriel de la DEN ({semestre}/{today.year})", body, sender)
    return 0


def demandes_en_attente(db: Session, today: datetime.date, sender) -> int:
    lines = []
    for d in db.query(models.DemandeAdhesion).all():
        if not d.is_open:
            continue
        age = (today - d.created_at.date()).days
        if d.etat == "nouvelle" and age >= DEMANDE_A_EXAMINER_JOURS and _claim(db, f"demande-examen:{d.id}"):
            lines.append(f"- {d.sigle} ({d.code}) : demande reçue il y a {age} jours, pas encore examinée")
        if d.avis_ca is None and age >= DEMANDE_AVIS_CA_JOURS and _claim(db, f"demande-avis:{d.id}"):
            lines.append(f"- {d.sigle} ({d.code}) : avis écrit du CA attendu depuis {age} jours (Statuts art. 18)")
    if not lines:
        return 0
    body = "Demandes d'adhésion en attente :\n\n" + "\n".join(lines) + "\n\nElles se traitent dans « Adhésions ».\n"
    return _send_all(_emails(db, {"den", "secretaire"}), "PSIE — Demandes d'adhésion en attente", body, sender)


def audit_sensible(db: Session, today: datetime.date, sender) -> int:
    """Résumé quotidien, à l'administrateur, des actions sensibles de la veille (droits, comptes, suppressions…)."""
    from . import audit

    since = datetime.datetime.combine(today - datetime.timedelta(days=1), datetime.time.min)
    entries = [a for a in db.query(models.AuditLog).filter(models.AuditLog.created_at >= since,
                                                           models.AuditLog.created_at < datetime.datetime.combine(today, datetime.time.min))
               .order_by(models.AuditLog.id) if audit.is_sensitive(a)]
    if not entries or not _claim(db, f"audit:{today.isoformat()}"):
        return 0
    lines = [f"- {a.created_at:%H:%M} {a.user_email or 'système'} : {a.action} {a.entity}"
             f"{' #' + str(a.entity_id) if a.entity_id else ''}{' — ' + a.detail if a.detail else ''}" for a in entries[:100]]
    body = (f"Actions sensibles du {today - datetime.timedelta(days=1):%d/%m/%Y} ({len(entries)}) :\n\n" + "\n".join(lines) +
            "\n\nLe détail complet et l'export se trouvent dans le Journal d'audit de la plateforme.\n")
    return _send_all(_emails(db, {"admin"}), "PSIE — Actions sensibles de la veille", body, sender)


def send_regulatory_reminders(db: Session, today: datetime.date | None = None, sender=None) -> int:
    today = today or datetime.date.today()
    sender = sender or send_email          # résolu à l'appel : remplaçable dans les tests
    sent = (mandats_a_echeance(db, today, sender) + rapport_semestriel(db, today, sender)
            + demandes_en_attente(db, today, sender)
            + audit_sensible(db, today, sender))
    db.commit()
    return sent
