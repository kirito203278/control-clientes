"""APScheduler dentro del proceso. Diario 12:00 (renovaciones y prórrogas) y 12:10 (purga), hora de México.
Respaldo: POST /api/jobs/run/{nombre} para cron-job.org (el hosting gratuito puede dormir el proceso)."""
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.jobs import tareas

log = logging.getLogger("jobs.scheduler")
_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    s = BackgroundScheduler(timezone=ZoneInfo(get_settings().tz))
    for nombre, hora, minuto in (("renovaciones", 12, 0), ("prorrogas", 12, 0), ("purga_no_renovados", 12, 10)):
        s.add_job(tareas.ejecutar, CronTrigger(hour=hora, minute=minuto), args=[nombre, "scheduler"], id=nombre,
                  replace_existing=True, misfire_grace_time=3600, coalesce=True)
    s.start()
    _scheduler = s
    log.info("Scheduler iniciado (tz=%s)", get_settings().tz)
    return s


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
