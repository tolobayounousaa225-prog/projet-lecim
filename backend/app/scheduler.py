"""Tâches planifiées de l'application (sauvegarde nocturne, rappels de réunions...).
Un seul scheduler en arrière-plan, démarré/arrêté avec le cycle de vie de l'app FastAPI."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .backup import create_backup
from .courrier_reminders import check_overdue_courrier
from .offsite_backup import sync_latest_backup
from .mandates import check_mandate_expirations
from .newsletter import run_monthly_newsletter
from .reminders import run_daily_reminders, run_visio_reminders
from .taches_reminders import check_overdue_taches

logger = logging.getLogger("lecim.scheduler")

scheduler = BackgroundScheduler()


def _run_backup_job() -> None:
    try:
        backup_path = create_backup()
    except Exception:
        logger.exception("Échec de la sauvegarde automatique planifiée")
        return
    # Échec séparé et non bloquant : un problème réseau/Git sur la copie
    # hors-site ne doit jamais faire paraître la sauvegarde locale en échec.
    sync_latest_backup(backup_path)


def _run_reminders_job() -> None:
    try:
        run_daily_reminders()
    except Exception:
        logger.exception("Échec de l'envoi des rappels de réunions")


def _run_visio_reminders_job() -> None:
    try:
        run_visio_reminders()
    except Exception:
        logger.exception("Échec de l'envoi des rappels programmés de visioconférence")


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


def _run_taches_reminders_job() -> None:
    try:
        check_overdue_taches()
    except Exception:
        logger.exception("Échec de la vérification des tâches en retard")


def _run_courrier_reminders_job() -> None:
    try:
        check_overdue_courrier()
    except Exception:
        logger.exception("Échec de la vérification du courrier sans réponse")


def start() -> None:
    scheduler.add_job(_run_backup_job, "cron", hour=2, minute=0, id="daily_backup", replace_existing=True)
    scheduler.add_job(_run_reminders_job, "cron", hour=7, minute=0, id="daily_reminders", replace_existing=True)
    scheduler.add_job(_run_mandates_job, "cron", hour=7, minute=15, id="daily_mandates", replace_existing=True)
    scheduler.add_job(
        _run_visio_reminders_job, "interval", minutes=10, id="visio_reminders", replace_existing=True
    )
    scheduler.add_job(
        _run_taches_reminders_job, "cron", hour=7, minute=30, id="daily_taches_reminders", replace_existing=True
    )
    scheduler.add_job(
        _run_courrier_reminders_job, "cron", hour=7, minute=45, id="daily_courrier_reminders", replace_existing=True
    )
    scheduler.add_job(
        _run_newsletter_job, "cron", day=1, hour=8, minute=0, id="monthly_newsletter", replace_existing=True
    )
    scheduler.start()


def shutdown() -> None:
    scheduler.shutdown(wait=False)
