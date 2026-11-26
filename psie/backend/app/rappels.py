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
ETATS_AVANT_AG_JOURS = 15               # Statuts art. 36 : états financiers à disposition quinze jours avant l'assemblée
ETATS_ALERTE_AVANT_AG_JOURS = 20        # on prévient 5 jours avant la date limite de mise à disposition


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


def etats_avant_ag(db: Session, today: datetime.date, sender) -> int:
    sent = 0
    upcoming = (db.query(models.Assemblee).filter(models.Assemblee.statut.in_(("preparation", "convoquee")),
                                                  models.Assemblee.type.in_(("AGA", "AGO"))).all())
    for a in upcoming:
        days = (a.date_assemblee - today).days
        if not 0 <= days <= ETATS_ALERTE_AVANT_AG_JOURS or not _claim(db, f"etats-ag:{a.id}"):
            continue
        limite = a.date_assemblee - datetime.timedelta(days=ETATS_AVANT_AG_JOURS)
        body = (f"{a.type_label} du {a.date_assemblee:%d/%m/%Y} ({a.lieu}).\n\nLes états financiers doivent être mis à "
                f"disposition des membres au plus tard le {limite:%d/%m/%Y} (quinze jours avant l'assemblée, Statuts art. 36). "
                "Ils se génèrent dans « Finances > État financier ».\n")
        sent += _send_all(_emails(db, {"finances", "den"}), "PSIE — États financiers à préparer avant l'AG", body, sender)
    return sent


def send_regulatory_reminders(db: Session, today: datetime.date | None = None, sender=None) -> int:
    today = today or datetime.date.today()
    sender = sender or send_email          # résolu à l'appel : remplaçable dans les tests
    sent = (mandats_a_echeance(db, today, sender) + rapport_semestriel(db, today, sender) + etats_avant_ag(db, today, sender))
    db.commit()
    return sent
