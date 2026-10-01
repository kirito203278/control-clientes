"""APScheduler dentro del proceso, hora de México:
  * renovaciones y prórrogas: 00:05 (poco después de las 23:59 en que termina el contrato) y 12:00
  * purga de No renovados (1 año): 12:10
Respaldo: POST /api/jobs/run/{nombre} para cron-job.org (el hosting gratuito puede dormir el proceso)."""
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.jobs import tareas

log = logging.getLogger("jobs.scheduler")
_scheduler: BackgroundScheduler | None = None

HORARIOS = {
    "renovaciones": [(0, 5), (12, 0)],
    "prorrogas": [(0, 5), (12, 0)],
    "purga_no_renovados": [(12, 10)],
}


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    tz = ZoneInfo(get_settings().tz)
    s = BackgroundScheduler(timezone=tz)
    for nombre, horas in HORARIOS.items():
        trigger = OrTrigger([CronTrigger(hour=h, minute=m, timezone=tz) for h, m in horas])
        s.add_job(tareas.ejecutar, trigger, args=[nombre, "scheduler"], id=nombre, replace_existing=True,
                  misfire_grace_time=3600, coalesce=True)
    s.start()
    _scheduler = s
    log.info("Scheduler iniciado (tz=%s)", get_settings().tz)
    return s


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
