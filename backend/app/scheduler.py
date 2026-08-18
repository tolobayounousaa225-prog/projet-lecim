"""Tâches planifiées de l'application (sauvegarde nocturne, rappels de réunions...).
Un seul scheduler en arrière-plan, démarré/arrêté avec le cycle de vie de l'app FastAPI."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .backup import create_backup
from .mandates import check_mandate_expirations
from .newsletter import run_monthly_newsletter
from .reminders import run_daily_reminders

logger = logging.getLogger("lecim.scheduler")

scheduler = BackgroundScheduler()


def _run_backup_job() -> None:
    try:
        create_backup()
    except Exception:
        logger.exception("Échec de la sauvegarde automatique planifiée")


def _run_reminders_job() -> None:
    try:
        run_daily_reminders()
    except Exception:
        logger.exception("Échec de l'envoi des rappels de réunions")


def _run_mandates_job() -> None:
    try:
        check_mandate_expirations()
    except Exception:
        logger.exception("Échec de la vérification des mandats électifs")


def _run_newsletter_job() -> None:
    try:
        run_monthly_newsletter()
    except Exception:
        logger.exception("Échec de l'envoi de la newsletter mensuelle")


def start() -> None:
    scheduler.add_job(_run_backup_job, "cron", hour=2, minute=0, id="daily_backup", replace_existing=True)
    scheduler.add_job(_run_reminders_job, "cron", hour=7, minute=0, id="daily_reminders", replace_existing=True)
    scheduler.add_job(_run_mandates_job, "cron", hour=7, minute=15, id="daily_mandates", replace_existing=True)
    scheduler.add_job(
        _run_newsletter_job, "cron", day=1, hour=8, minute=0, id="monthly_newsletter", replace_existing=True
    )
    scheduler.start()


def shutdown() -> None:
    scheduler.shutdown(wait=False)
