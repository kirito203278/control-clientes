"""Reglas derivadas de un ciclo de paquete: estado efectivo, semáforo, saldo, prórroga."""
import datetime as dt
from decimal import Decimal

from app.config import get_settings
from app.models import PaqueteCliente
from app.services.periodos import quincena_de

VIGENTES = ("activo", "vencido")                 # ciclos "abiertos" que cuentan para el cliente
COBRABLES = ("activo", "vencido", "renovado")    # aún admiten pagos (un ciclo renovado puede conservar deuda)
ORDEN_SEMAFORO = {"rojo": 0, "amarillo": 1, "gris": 2, "verde": 3}


def dias_para_renovar(p: PaqueteCliente, hoy: dt.date) -> int:
    return (p.fecha_renovacion - hoy).days


def pagado_hasta(p: PaqueteCliente, corte: dt.date | None = None) -> Decimal:
    return sum((g.monto for g in p.pagos if corte is None or g.fecha <= corte), Decimal("0"))


def estado_efectivo(p: PaqueteCliente, hoy: dt.date) -> str:
    """'por_vencer' no se guarda: es un activo sin decisión al que faltan <= aviso días (aviso = R-4)."""
    if p.estado == "activo" and p.renovacion_decision == "pendiente":
        if 0 <= dias_para_renovar(p, hoy) <= get_settings().aviso_dias_antes_renovacion:
            return "por_vencer"
    return p.estado


def semaforo(p: PaqueteCliente, hoy: dt.date) -> str:
    """rojo = vencido sin decisión · verde = renovación pagada · amarillo = confirmada sin pago · gris = pendiente."""
    if p.estado == "vencido" and p.renovacion_decision == "pendiente":
        return "rojo"
    if p.estado in ("archivado", "eliminado"):
        return "gris"
    if pagado_hasta(p) >= p.costo:
        return "verde"
    if p.renovacion_decision == "si":
        return "amarillo"
    return "gris"


def prorroga_vencida(p: PaqueteCliente, hoy: dt.date) -> bool:
    return p.prorroga_hasta is not None and p.prorroga_hasta < hoy and pagado_hasta(p) < p.costo


def requiere_prorroga(p: PaqueteCliente, hoy: dt.date) -> bool:
    """Terminó la tolerancia de pago, sigue debiendo y no hay prórroga registrada."""
    if p.estado not in COBRABLES or p.prorroga_hasta is not None:
        return False
    limite = p.fecha_renovacion + dt.timedelta(days=get_settings().tolerancia_dias)
    return hoy > limite and pagado_hasta(p) < p.costo


def recalcular_pagada(p: PaqueteCliente) -> None:
    p.renovacion_pagada = pagado_hasta(p) >= p.costo


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
        "semaforo": semaforo(p, hoy),
        "prorroga_hasta": p.prorroga_hasta, "prorroga_registrada_en": p.prorroga_registrada_en,
        "prorroga_dias_restantes": (p.prorroga_hasta - hoy).days if p.prorroga_hasta else None,
        "prorroga_vencida": prorroga_vencida(p, hoy), "requiere_prorroga": requiere_prorroga(p, hoy),
        "ciclo_anterior_id": p.ciclo_anterior_id, "archivado_en": p.archivado_en,
    }
