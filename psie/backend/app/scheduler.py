"""Tâches planifiées : cotisations de l'année, relances, résumé hebdomadaire."""

import datetime
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from . import models
from .config import settings
from .database import SessionLocal
from .finance import generate_annual_echeances, send_reminders, send_weekly_digest

logger = logging.getLogger("psie.scheduler")
_scheduler: BackgroundScheduler | None = None


def job_daily() -> None:
    """Chaque jour : crée les cotisations de l'année en cours si le montant est défini, puis
    envoie les relances dues."""
    db = SessionLocal()
    try:
        year = datetime.date.today().year
        if db.query(models.BaremeCotisation).filter_by(annee=year).first():
            created = generate_annual_echeances(db, year)
            db.commit()
            if created:
                logger.info("%d cotisation(s) annuelle(s) %d créée(s)", created, year)
        sent = send_reminders(db)
        if sent:
            logger.info("%d relance(s) envoyée(s)", sent)
    except Exception:
        logger.exception("Échec de la tâche quotidienne")
        db.rollback()
    finally:
        db.close()


def job_weekly_digest() -> None:
    db = SessionLocal()
    try:
        send_weekly_digest(db)
    except Exception:
        logger.exception("Échec du résumé hebdomadaire")
    finally:
        db.close()


def start() -> None:
    global _scheduler
    if not settings.scheduler_enabled or _scheduler:
        return
    _scheduler = BackgroundScheduler(timezone="Africa/Abidjan")
    _scheduler.add_job(job_daily, "cron", hour=7, minute=0, id="daily", replace_existing=True)
    _scheduler.add_job(job_weekly_digest, "cron", day_of_week="mon", hour=7, minute=30, id="digest", replace_existing=True)
    _scheduler.start()


def shutdown() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
