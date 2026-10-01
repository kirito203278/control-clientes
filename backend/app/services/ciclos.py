"""Reglas derivadas de un ciclo de paquete: vencimiento, bloqueo, semáforo, saldo y prórroga.

Línea de tiempo (R = fecha de renovación; el contrato termina R a las 23:59, hora de México):
  * R-4 .. R      aviso «¿renueva?» ("por vencer")
  * R+1 en adelante, sin decisión  ->  el paquete queda BLOQUEADO (ventana que no se puede cerrar).
        Opciones: Renovó (solo si ya pagó completo) · No renovó · Solicitó prórroga (solo si debe, una vez)
  * Prórroga: 5 días naturales fijos desde que se activa; admite pagos parciales o el resto.
        Si vence sin pago completo -> el cliente pasa solo a No renovados.
  * Sin decisión: `dias_para_decidir` (2) días de bloqueo y pasa solo a No renovados.
No hay días de tolerancia de pago.
"""
import datetime as dt
from decimal import Decimal

from app.config import get_settings
from app.models import PaqueteCliente
from app.services.periodos import quincena_de

VIGENTES = ("activo", "vencido")                 # ciclos "abiertos" que cuentan para el cliente
COBRABLES = ("activo", "vencido", "renovado")    # aún admiten pagos (un ciclo renovado puede conservar deuda histórica)
ORDEN_SEMAFORO = {"rojo": 0, "amarillo": 1, "gris": 2, "verde": 3}


def dias_para_renovar(p: PaqueteCliente, hoy: dt.date) -> int:
    return (p.fecha_renovacion - hoy).days


def pagado_hasta(p: PaqueteCliente, corte: dt.date | None = None) -> Decimal:
    return sum((g.monto for g in p.pagos if corte is None or g.fecha <= corte), Decimal("0"))


def pagado_completo(p: PaqueteCliente) -> bool:
    return pagado_hasta(p) >= p.costo


def es_vencido(p: PaqueteCliente, hoy: dt.date) -> bool:
    """Pasó su fecha de renovación (desde las 23:59 de R) sin decisión. Se deriva de la fecha, no del job."""
    return p.estado in VIGENTES and p.renovacion_decision == "pendiente" and hoy > p.fecha_renovacion


def prorroga_activa(p: PaqueteCliente, hoy: dt.date) -> bool:
    return p.prorroga_hasta is not None and hoy <= p.prorroga_hasta and not pagado_completo(p)


def prorroga_vencida(p: PaqueteCliente, hoy: dt.date) -> bool:
    return p.prorroga_hasta is not None and hoy > p.prorroga_hasta and not pagado_completo(p)


def bloqueado(p: PaqueteCliente, hoy: dt.date) -> bool:
    """Ventana de bloqueo: vencido sin decisión y sin una prórroga corriendo."""
    return es_vencido(p, hoy) and not prorroga_activa(p, hoy)


def limite_decision(p: PaqueteCliente) -> dt.date:
    """Último día con la ventana activa. Después (00:05 del día siguiente) pasa solo a No renovados."""
    base = p.prorroga_hasta or p.fecha_renovacion
    return base + dt.timedelta(days=get_settings().dias_para_decidir)


def opciones_bloqueo(p: PaqueteCliente, hoy: dt.date) -> list[str]:
    if not bloqueado(p, hoy):
        return []
    if pagado_completo(p):
        return ["renovo", "no_renovo"]
    return ["no_renovo"] if p.prorroga_hasta is not None else ["no_renovo", "prorroga"]


def estado_efectivo(p: PaqueteCliente, hoy: dt.date) -> str:
    """'vencido' y 'por_vencer' se calculan: no dependen de que haya corrido el job."""
    if es_vencido(p, hoy):
        return "vencido"
    if p.estado == "activo" and p.renovacion_decision == "pendiente":
        if 0 <= dias_para_renovar(p, hoy) <= get_settings().aviso_dias_antes_renovacion:
            return "por_vencer"
    return p.estado


def semaforo(p: PaqueteCliente, hoy: dt.date) -> str:
    """rojo = vencido sin decisión · verde = renovación pagada · amarillo = confirmada sin pago · gris = pendiente."""
    if es_vencido(p, hoy):
        return "rojo"
    if p.estado in ("archivado", "eliminado"):
        return "gris"
    if pagado_completo(p):
        return "verde"
    if p.renovacion_decision == "si":
        return "amarillo"
    return "gris"


def recalcular_pagada(p: PaqueteCliente) -> None:
    p.renovacion_pagada = pagado_completo(p)


def paquete_out(p: PaqueteCliente, hoy: dt.date) -> dict:
    pagado = pagado_hasta(p)
    avance = float(min(Decimal(1), pagado / p.costo)) * 100 if p.costo > 0 else 100.0
    return {
        "id": p.id, "cliente_id": p.cliente_id,
        "paquete_id": p.paquete_id, "paquete": p.paquete.nombre,
        "tipo_id": p.tipo_id, "tipo": p.tipo.nombre,
        "costo": p.costo, "pagado": pagado, "restante": max(p.costo - pagado, Decimal(0)),
        "avance_pct": round(avance, 1),
        "fecha_inicio": p.fecha_inicio, "fecha_renovacion": p.fecha_renovacion,
        "quincena": quincena_de(p.fecha_renovacion),
        "dias_para_renovar": dias_para_renovar(p, hoy),
        "estado": p.estado, "estado_efectivo": estado_efectivo(p, hoy),
        "renovacion_decision": p.renovacion_decision, "renovacion_pagada": p.renovacion_pagada,
        "no_renovara": p.estado in VIGENTES and p.renovacion_decision == "no",   # marcado: se archiva al terminar el contrato
        "semaforo": semaforo(p, hoy),
        "bloqueado": bloqueado(p, hoy), "opciones_bloqueo": opciones_bloqueo(p, hoy),
        "limite_decision": limite_decision(p) if es_vencido(p, hoy) else None,
        "prorroga_hasta": p.prorroga_hasta, "prorroga_registrada_en": p.prorroga_registrada_en,
        "prorroga_dias_restantes": (p.prorroga_hasta - hoy).days if p.prorroga_hasta else None,
        "prorroga_activa": prorroga_activa(p, hoy), "prorroga_vencida": prorroga_vencida(p, hoy),
        "ciclo_anterior_id": p.ciclo_anterior_id, "archivado_en": p.archivado_en,
    }


def veces_renovado(db, p: PaqueteCliente) -> int:
    """Renovaciones consecutivas con ESTE mismo paquete. Al renovar con otro paquete la cuenta se reinicia en 0
    (el historial de ciclos se conserva; solo cambia el contador)."""
    n, actual = 0, p
    while actual.ciclo_anterior_id is not None:
        anterior = db.get(PaqueteCliente, actual.ciclo_anterior_id)
        if anterior is None or anterior.paquete_id != p.paquete_id:
            break
        n, actual = n + 1, anterior
    return n
