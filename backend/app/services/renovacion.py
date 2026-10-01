"""Ciclo de vida de un paquete: renovar, no renovar (conservar/borrar), reingreso y purga."""
import datetime as dt
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import bitacora
from app.config import get_settings
from app.dates import ahora, hoy as hoy_mx
from app.models import ArchivoNoRenovado, Cliente, PaqueteCliente, Renovacion, Usuario
from app.services import ciclos, notificar
from app.services.periodos import restar_meses

TIPOS_AVISO = ("renovacion_3d", "paquete_vencido")


def _validar_cambio_catalogo(db: Session, p: PaqueteCliente, paquete_id: int, tipo_id: int) -> None:
    from app.models import CatalogoPaquete, CatalogoTipo
    if paquete_id != p.paquete_id:
        pq = db.get(CatalogoPaquete, paquete_id)
        if pq is None or not pq.activo:
            raise HTTPException(422, "Paquete inválido o desactivado")
    if tipo_id != p.tipo_id:
        tp = db.get(CatalogoTipo, tipo_id)
        if tp is None or not tp.activo:
            raise HTTPException(422, "Tipo inválido o desactivado")


def vigentes_del_cliente(db: Session, cliente_id: int, excepto: int | None = None) -> int:
    q = select(PaqueteCliente.id).where(PaqueteCliente.cliente_id == cliente_id,
                                        PaqueteCliente.estado.in_(ciclos.VIGENTES))
    if excepto is not None:
        q = q.where(PaqueteCliente.id != excepto)
    return len(db.scalars(q).all())


def enviar_a_no_renovados(db: Session, cliente: Cliente, motivo: str) -> None:
    cliente.estado = "no_renovado"
    db.add(ArchivoNoRenovado(cliente_id=cliente.id, cm_id=cliente.cm_id, motivo=motivo, archivado_en=ahora()))


def renovar(db: Session, user: Usuario, p: PaqueteCliente, *, paquete_id: int | None, tipo_id: int | None,
            costo: Decimal | None, fecha_renovacion: dt.date | None) -> PaqueteCliente:
    """Cierra el ciclo (conserva sus pagos y su deuda) y abre el siguiente con pagado = 0."""
    if p.estado not in ciclos.VIGENTES:
        raise HTTPException(409, "Este paquete ya no está vigente")
    if p.cliente.estado != "activo":
        raise HTTPException(409, "El cliente está en No renovados: usa el reingreso")
    nuevo_pq, nuevo_tp = paquete_id or p.paquete_id, tipo_id or p.tipo_id
    _validar_cambio_catalogo(db, p, nuevo_pq, nuevo_tp)
    nuevo_costo = p.costo if costo is None else costo
    nueva_fecha = fecha_renovacion or p.fecha_renovacion + dt.timedelta(days=get_settings().ciclo_dias)
    if nueva_fecha <= p.fecha_renovacion:
        raise HTTPException(422, "La nueva fecha de renovación debe ser posterior a la actual "
                                 f"({p.fecha_renovacion.strftime('%d/%m/%Y')})")
    nuevo = PaqueteCliente(cliente_id=p.cliente_id, paquete_id=nuevo_pq, tipo_id=nuevo_tp, costo=nuevo_costo,
                           fecha_inicio=p.fecha_renovacion, fecha_renovacion=nueva_fecha, ciclo_anterior_id=p.id)
    db.add(nuevo)
    db.flush()
    p.estado, p.renovacion_decision = "renovado", "si"
    ciclos.recalcular_pagada(p)
    db.add(Renovacion(ciclo_anterior_id=p.id, ciclo_nuevo_id=nuevo.id, paquete_anterior_id=p.paquete_id,
                      paquete_nuevo_id=nuevo_pq, costo_anterior=p.costo, costo_nuevo=nuevo_costo,
                      fecha=hoy_mx(), registrado_por=user.id))
    notificar.marcar_leidas_de_paquete(db, p.id, TIPOS_AVISO)
    bitacora.registrar_si_admin(db, user, "renovar_por_admin", {"paquete_id": p.id, "nuevo_id": nuevo.id})
    db.flush()
    db.refresh(nuevo)
    return nuevo


def no_renovar(db: Session, user: Usuario, p: PaqueteCliente, *, accion: str, confirmar_nombre: str | None,
               eliminar_cliente: bool | None) -> dict:
    if p.estado not in ciclos.VIGENTES:
        raise HTTPException(409, "Este paquete ya no está vigente")
    cliente = p.cliente
    es_ultimo = vigentes_del_cliente(db, cliente.id, excepto=p.id) == 0
    if accion == "borrar":
        if confirmar_nombre != p.paquete.nombre:
            raise HTTPException(422, f"Escribe el nombre exacto del paquete ({p.paquete.nombre}) para confirmar")
        if es_ultimo and eliminar_cliente is None:
            raise HTTPException(409, {"code": "ultimo_paquete",
                                      "mensaje": "Es el último paquete del cliente: ¿también se elimina el cliente?"})
    elif accion != "conservar":
        raise HTTPException(422, "accion debe ser 'conservar' o 'borrar'")

    detalle = {"paquete_id": p.id, "cliente_id": cliente.id, "accion": accion}
    if accion == "borrar" and es_ultimo and eliminar_cliente:
        bitacora.registrar(db, user, "borrar_paquete_y_cliente", {**detalle, "nombre": cliente.nombre})
        db.delete(cliente)
        db.flush()
        return {"cliente_eliminado": True, "cliente_a_no_renovados": False}

    p.renovacion_decision = "no"
    p.estado = "archivado" if accion == "conservar" else "eliminado"
    p.archivado_en = ahora()
    notificar.marcar_leidas_de_paquete(db, p.id, TIPOS_AVISO)
    a_no_renovados = False
    if es_ultimo:
        enviar_a_no_renovados(db, cliente, "Decidió no renovar" if accion == "conservar" else "Paquete eliminado")
        a_no_renovados = True
    bitacora.registrar(db, user, "no_renovar" if accion == "conservar" else "borrar_paquete",
                       {**detalle, "cliente_a_no_renovados": a_no_renovados})
    db.flush()
    return {"cliente_eliminado": False, "cliente_a_no_renovados": a_no_renovados}


def reingresar(db: Session, user: Usuario, cliente: Cliente, *, modo: str, paquete_id: int | None,
               tipo_id: int | None, costo: Decimal | None, fecha_renovacion: dt.date | None) -> PaqueteCliente:
    """<2 meses en No renovados: continuar el paquete anterior o crear uno nuevo conservando historial.
    >=2 meses: se fuerza paquete nuevo y se BORRA el historial anterior."""
    s = get_settings()
    if cliente.estado != "no_renovado":
        raise HTTPException(409, "El cliente no está en No renovados")
    archivo = db.scalars(select(ArchivoNoRenovado).where(
        ArchivoNoRenovado.cliente_id == cliente.id, ArchivoNoRenovado.reingresado_en.is_(None))
        .order_by(ArchivoNoRenovado.archivado_en.desc())).first()
    if modo not in ("continuar", "nuevo"):
        raise HTTPException(422, "modo debe ser 'continuar' o 'nuevo'")
    ahora_ = ahora()
    forzar_nuevo = archivo is not None and archivo.archivado_en <= restar_meses(ahora_, s.reingreso_meses)
    hoy = hoy_mx()
    fecha = fecha_renovacion or hoy + dt.timedelta(days=s.ciclo_dias)
    if fecha <= hoy:
        raise HTTPException(422, "La fecha de renovación debe ser posterior a hoy")

    anterior = None
    if forzar_nuevo:
        if modo == "continuar":
            raise HTTPException(422, f"Pasaron {s.reingreso_meses} meses o más: debes crear un paquete nuevo "
                                     "(el historial anterior se borrará)")
        if paquete_id is None or tipo_id is None or costo is None:
            raise HTTPException(422, "Indica paquete, tipo y costo del paquete nuevo")
        db.execute(delete(PaqueteCliente).where(PaqueteCliente.cliente_id == cliente.id))
        db.expire(cliente, ["paquetes"])
        historial_borrado = True
    else:
        historial_borrado = False
        if modo == "continuar":
            anterior = db.scalars(select(PaqueteCliente).where(
                PaqueteCliente.cliente_id == cliente.id, PaqueteCliente.estado == "archivado")
                .order_by(PaqueteCliente.archivado_en.desc())).first()
            if anterior is None:
                raise HTTPException(422, "No hay un paquete anterior que continuar: crea uno nuevo")
            paquete_id, tipo_id = anterior.paquete_id, anterior.tipo_id
            costo = anterior.costo if costo is None else costo
        elif paquete_id is None or tipo_id is None or costo is None:
            raise HTTPException(422, "Indica paquete, tipo y costo del paquete nuevo")

    from app.routers.clientes import validar_catalogos
    if not (modo == "continuar" and anterior is not None):
        validar_catalogos(db, paquete_id, tipo_id)
    nuevo = PaqueteCliente(cliente_id=cliente.id, paquete_id=paquete_id, tipo_id=tipo_id, costo=costo,
                           fecha_inicio=hoy, fecha_renovacion=fecha,
                           ciclo_anterior_id=anterior.id if anterior else None)
    db.add(nuevo)
    cliente.estado = "activo"
    if archivo is not None:
        archivo.reingresado_en = ahora_
    bitacora.registrar(db, user, "reingreso", {"cliente_id": cliente.id, "modo": modo,
                                               "historial_borrado": historial_borrado})
    db.flush()
    db.refresh(nuevo)
    return nuevo


def purgar_no_renovados(db: Session, ahora_: dt.datetime | None = None) -> list[str]:
    """Elimina definitivamente a los clientes con `purga_meses` o más en No renovados."""
    ahora_ = ahora_ or ahora()
    limite = restar_meses(ahora_, get_settings().purga_meses)
    filas = db.execute(select(ArchivoNoRenovado, Cliente).join(Cliente, Cliente.id == ArchivoNoRenovado.cliente_id)
                       .where(ArchivoNoRenovado.reingresado_en.is_(None), ArchivoNoRenovado.archivado_en <= limite,
                              Cliente.estado == "no_renovado")).all()
    eliminados = []
    for archivo, cliente in filas:
        if vigentes_del_cliente(db, cliente.id) > 0:       # por seguridad: nunca purgar a quien tenga paquetes vigentes
            continue
        eliminados.append(cliente.nombre)
        bitacora.registrar(db, None, "purga_no_renovados", {"cliente_id": cliente.id, "nombre": cliente.nombre,
                                                            "archivado_en": archivo.archivado_en.isoformat()})
        db.delete(cliente)
    db.flush()
    return eliminados
