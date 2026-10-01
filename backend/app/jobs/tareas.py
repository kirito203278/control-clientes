"""Tareas programadas. Idempotentes: se pueden correr varias veces el mismo día sin duplicar efectos
(notificaciones con dedupe_key, estados filtrados por fecha)."""
import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.dates import hoy as hoy_mx
from app.database import get_sessionmaker
from app.models import JobEjecucion, PaqueteCliente
from app.services import ciclos, notificar
from app.services.renovacion import purgar_no_renovados

log = logging.getLogger("jobs")


def _fmt(f: dt.date) -> str:
    return f.strftime("%d/%m/%Y")


def _paquetes(db: Session, *condiciones):
    return db.scalars(select(PaqueteCliente).where(*condiciones).options(
        selectinload(PaqueteCliente.cliente), selectinload(PaqueteCliente.paquete), selectinload(PaqueteCliente.pagos)))


def avisos_renovacion(db: Session, hoy: dt.date | None = None) -> dict:
    """12:00 · avisa 4 días antes de la renovación (3 días antes de la fecha límite R-1) y marca como
    vencidos los paquetes que llegaron a su fecha sin decisión, notificando al CM."""
    hoy = hoy or hoy_mx()
    aviso = get_settings().aviso_dias_antes_renovacion
    avisos = vencidos = 0
    for p in _paquetes(db, PaqueteCliente.estado == "activo", PaqueteCliente.renovacion_decision == "pendiente",
                       PaqueteCliente.fecha_renovacion <= hoy + dt.timedelta(days=aviso)).all():
        c, dias = p.cliente, (p.fecha_renovacion - hoy).days
        if c.estado != "activo":
            continue
        if dias <= 0:
            p.estado = "vencido"
            vencidos += 1
            notificar.crear(db, c, "paquete_vencido",
                            f"{c.nombre}: el paquete {p.paquete.nombre} llegó a su fecha de renovación "
                            f"({_fmt(p.fecha_renovacion)}) sin decisión. ¿Renovó?",
                            f"vencido:{p.id}", paquete_id=p.id)
        else:
            avisos += notificar.crear(
                db, c, "renovacion_3d",
                f"{c.nombre}: el paquete {p.paquete.nombre} renueva el {_fmt(p.fecha_renovacion)} "
                f"({'mañana' if dias == 1 else f'en {dias} días'}). ¿Renueva?", f"renov:{p.id}", paquete_id=p.id)
    db.commit()
    return {"avisos": avisos, "marcados_vencidos": vencidos}


def avisos_prorroga(db: Session, hoy: dt.date | None = None) -> dict:
    """12:00 · avisa 3 días antes de vencer una prórroga y, si venció sin pago completo, pregunta si el cliente pagó."""
    hoy = hoy or hoy_mx()
    margen = get_settings().aviso_prorroga_dias
    proximas = vencidas = 0
    for p in _paquetes(db, PaqueteCliente.prorroga_hasta.is_not(None), PaqueteCliente.estado.in_(ciclos.COBRABLES),
                       PaqueteCliente.prorroga_hasta <= hoy + dt.timedelta(days=margen)).all():
        if ciclos.pagado_hasta(p) >= p.costo:
            continue
        c, resta = p.cliente, p.costo - ciclos.pagado_hasta(p)
        if p.prorroga_hasta < hoy:
            vencidas += notificar.crear(
                db, c, "prorroga_vencida",
                f"{c.nombre}: la prórroga del paquete {p.paquete.nombre} venció el {_fmt(p.prorroga_hasta)} y aún "
                f"faltan ${resta:,.2f}. ¿El cliente pagó?", f"prorroga-venc:{p.id}:{p.prorroga_hasta}",
                paquete_id=p.id, requiere_respuesta=True)
        else:
            d = (p.prorroga_hasta - hoy).days
            proximas += notificar.crear(
                db, c, "prorroga_3d",
                f"{c.nombre}: la prórroga del paquete {p.paquete.nombre} vence el {_fmt(p.prorroga_hasta)} "
                f"({'hoy' if d == 0 else f'en {d} días'}); faltan ${resta:,.2f}.",
                f"prorroga-3d:{p.id}:{p.prorroga_hasta}", paquete_id=p.id)
    db.commit()
    return {"avisos_prorroga": proximas, "prorrogas_vencidas": vencidas}


def purga_no_renovados(db: Session) -> dict:
    """12:10 · elimina definitivamente a los clientes con 3 meses en No renovados."""
    eliminados = purgar_no_renovados(db)
    db.commit()
    return {"eliminados": len(eliminados)}


JOBS = {"renovaciones": avisos_renovacion, "prorrogas": avisos_prorroga, "purga_no_renovados": purga_no_renovados}


def ejecutar(nombre: str, origen: str = "manual") -> dict:
    """Corre un job con su propia sesión y deja registro en jobs_ejecuciones."""
    with get_sessionmaker()() as db:
        try:
            resultado = JOBS[nombre](db)
        except Exception:
            db.rollback()
            log.exception("Falló el job %s", nombre)
            raise
        db.add(JobEjecucion(nombre=nombre, origen=origen, resultado=resultado))
        db.commit()
        return resultado
