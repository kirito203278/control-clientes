"""Respaldo para cron externo (cron-job.org): el hosting gratuito duerme el proceso y APScheduler puede no
estar despierto a las 12:00. La propia llamada lo despierta y ejecuta el job. Protegido con X-Jobs-Secret,
no con JWT: quien llama es un servicio, no una persona."""
import hmac

from fastapi import APIRouter, Header, HTTPException

from app.config import get_settings
from app.jobs import tareas

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("/run/{nombre}")
def run_job(nombre: str, x_jobs_secret: str = Header(default="")):
    if not hmac.compare_digest(x_jobs_secret.encode(), get_settings().jobs_secret.encode()):
        raise HTTPException(401, "Secreto inválido")
    if nombre not in tareas.JOBS:
        raise HTTPException(404, "Job no encontrado")
    return {"ok": True, "job": nombre, "resultado": tareas.ejecutar(nombre, "endpoint")}
