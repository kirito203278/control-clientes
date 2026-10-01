"""Clientes y su ficha. Todo acceso pasa por services/scope.py (aislamiento por cm_id)."""
import datetime as dt
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import bitacora
from app.config import get_settings
from app.database import get_db
from app.dates import hoy as hoy_mx
from app.deps import get_current_user, require_admin_write, require_writer
from app.models import (ArchivoNoRenovado, CatalogoPaquete, CatalogoTipo, Cliente, PaqueteCliente, Usuario)
from app.security.crypto import decrypt_value, encrypt_value
from app.services import bloqueo, ciclos
from app.services.scope import clientes_q, obtener_cliente

router = APIRouter(prefix="/api/clientes", tags=["clientes"])


class PaqueteNuevo(BaseModel):
    paquete_id: int
    tipo_id: int
    costo: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    fecha_inicio: dt.date | None = None      # se captura el INICIO; la renovación se calcula sola (+30 días)


class ClienteIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=160)
    correo_fb: str | None = None
    password_fb: str | None = None
    correo_contacto: str | None = None
    telefono: str | None = None
    observaciones: str | None = None
    cm_id: int | None = None          # solo lo usa un admin; un CM siempre queda como dueño
    paquetes: list[PaqueteNuevo] = []


class ClientePatch(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=160)
    correo_fb: str | None = None
    password_fb: str | None = None
    correo_contacto: str | None = None
    telefono: str | None = None
    observaciones: str | None = None


class ReasignarIn(BaseModel):
    cm_id: int | None = None


def validar_catalogos(db: Session, paquete_id: int, tipo_id: int) -> None:
    pq, tp = db.get(CatalogoPaquete, paquete_id), db.get(CatalogoTipo, tipo_id)
    if pq is None or not pq.activo:
        raise HTTPException(422, "Paquete inválido o desactivado")
    if tp is None or not tp.activo:
        raise HTTPException(422, "Tipo inválido o desactivado")


def tipo_id_ok(datos: PaqueteNuevo) -> int:
    return datos.tipo_id


def crear_ciclo(db: Session, cliente: Cliente, datos: PaqueteNuevo) -> PaqueteCliente:
    validar_catalogos(db, datos.paquete_id, datos.tipo_id)
    inicio = datos.fecha_inicio or hoy_mx()
    p = PaqueteCliente(cliente_id=cliente.id, paquete_id=datos.paquete_id, tipo_id=tipo_id_ok(datos), costo=datos.costo,
                       fecha_inicio=inicio, fecha_renovacion=inicio + dt.timedelta(days=get_settings().ciclo_dias))
    db.add(p)
    db.flush()
    return p


def _cargar(db: Session, q):
    return db.scalars(q.options(selectinload(Cliente.paquetes).selectinload(PaqueteCliente.pagos),
                                selectinload(Cliente.paquetes).selectinload(PaqueteCliente.paquete),
                                selectinload(Cliente.paquetes).selectinload(PaqueteCliente.tipo))).all()


def _resumen(c: Cliente, hoy: dt.date, cms: dict[int, str]) -> dict:
    vig = [p for p in c.paquetes if p.estado in ciclos.VIGENTES]
    sem = min((ciclos.semaforo(p, hoy) for p in vig), key=lambda s: ciclos.ORDEN_SEMAFORO[s], default=None)
    return {"id": c.id, "nombre": c.nombre, "estado": c.estado, "cm_id": c.cm_id,
            "cm_nombre": cms.get(c.cm_id) if c.cm_id else None, "telefono": c.telefono,
            "paquetes_vigentes": len(vig), "semaforo": sem,
            "pendiente_decision": any(ciclos.bloqueado(p, hoy) for p in vig),
            "quincenas": sorted({ciclos.quincena_de(p.fecha_renovacion) for p in vig}),
            "proxima_renovacion": min((p.fecha_renovacion for p in vig), default=None)}


@router.get("")
def listar(quincena: int | None = Query(default=None, ge=1, le=2), estado: str = "activo", q: str | None = None,
           cm_id: int | None = None, por_reasignar: bool = False, db: Session = Depends(get_db),
           user: Usuario = Depends(get_current_user)):
    if estado not in ("activo", "no_renovado", "todos"):
        raise HTTPException(422, "estado inválido")
    consulta = clientes_q(user).order_by(Cliente.nombre)
    if estado != "todos":
        consulta = consulta.where(Cliente.estado == estado)
    if user.rol == "admin":                       # un CM nunca puede filtrar por otro cm_id
        if por_reasignar:
            consulta = consulta.where(Cliente.cm_id.is_(None))
        elif cm_id is not None:
            consulta = consulta.where(Cliente.cm_id == cm_id)
    if q:
        consulta = consulta.where(Cliente.nombre.ilike(f"%{q.strip()}%"))
    hoy = hoy_mx()
    cms = {u.id: u.nombre for u in db.scalars(select(Usuario).where(Usuario.rol == "cm"))}
    filas = [_resumen(c, hoy, cms) for c in _cargar(db, consulta)]
    if quincena is not None and estado == "activo":
        filas = [f for f in filas if quincena in f["quincenas"]]
    return filas


@router.post("", status_code=status.HTTP_201_CREATED)
def crear(datos: ClienteIn, db: Session = Depends(get_db), user: Usuario = Depends(require_writer)):
    if user.rol == "cm":
        cm_id = user.id
    else:
        cm_id = datos.cm_id
        if cm_id is not None:
            cm = db.get(Usuario, cm_id)
            if cm is None or cm.rol != "cm" or not cm.activo:
                raise HTTPException(422, "El CM indicado no existe o está dado de baja")
    if len(datos.paquetes) > 1:
        raise HTTPException(422, "Un cliente tiene un solo paquete")
    c = Cliente(cm_id=cm_id, nombre=datos.nombre.strip(), correo_contacto=datos.correo_contacto,
                telefono=datos.telefono, observaciones=datos.observaciones,
                correo_fb_enc=encrypt_value(datos.correo_fb) if datos.correo_fb else None,
                password_fb_enc=encrypt_value(datos.password_fb) if datos.password_fb else None)
    db.add(c)
    db.flush()
    for pq in datos.paquetes:
        crear_ciclo(db, c, pq)
    if user.rol == "admin":
        bitacora.registrar(db, user, "alta_cliente_admin", {"cliente_id": c.id, "cm_id": cm_id})
    db.commit()
    return {"id": c.id}


def ficha_out(c: Cliente, hoy: dt.date, db: Session) -> dict:
    ordenados = sorted(c.paquetes, key=lambda p: (p.fecha_renovacion, p.id), reverse=True)
    vigentes = [ciclos.paquete_out(p, hoy) for p in sorted(c.paquetes, key=lambda p: p.fecha_renovacion)
                if p.estado in ciclos.VIGENTES]
    historial = [ciclos.paquete_out(p, hoy) for p in ordenados if p.estado not in ciclos.VIGENTES
                 and p.estado != "eliminado"]
    archivo = db.scalars(select(ArchivoNoRenovado).where(ArchivoNoRenovado.cliente_id == c.id,
                                                         ArchivoNoRenovado.reingresado_en.is_(None))).first()
    return {"id": c.id, "nombre": c.nombre, "estado": c.estado, "cm_id": c.cm_id,
            "correo_fb": decrypt_value(c.correo_fb_enc) if c.correo_fb_enc else None,
            "tiene_password_fb": bool(c.password_fb_enc),
            "correo_contacto": c.correo_contacto, "telefono": c.telefono, "observaciones": c.observaciones,
            "paquetes": vigentes, "historial": historial,
            "no_renovado_desde": archivo.archivado_en if archivo else None}


@router.get("/{cliente_id}")
def ficha(cliente_id: int, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    c = obtener_cliente(db, user, cliente_id)
    return ficha_out(c, hoy_mx(), db)


@router.patch("/{cliente_id}")
def editar(cliente_id: int, datos: ClientePatch, db: Session = Depends(get_db),
           user: Usuario = Depends(require_writer)):
    c = obtener_cliente(db, user, cliente_id)
    bloqueo.exigir_libre(db, c.id, hoy_mx())
    campos = datos.model_dump(exclude_unset=True)
    if "nombre" in campos and campos["nombre"]:
        c.nombre = campos["nombre"].strip()
    for k in ("correo_contacto", "telefono", "observaciones"):
        if k in campos:
            setattr(c, k, campos[k] or None)
    if "correo_fb" in campos:
        c.correo_fb_enc = encrypt_value(campos["correo_fb"]) if campos["correo_fb"] else None
    if "password_fb" in campos and campos["password_fb"]:      # vacío = no cambiar
        c.password_fb_enc = encrypt_value(campos["password_fb"])
    if user.rol == "admin":
        bitacora.registrar(db, user, "editar_cliente_admin", {"cliente_id": c.id, "campos": sorted(campos)})
    db.commit()
    return ficha_out(c, hoy_mx(), db)


@router.post("/{cliente_id}/password-fb/ver")
def ver_password(cliente_id: int, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    c = obtener_cliente(db, user, cliente_id)
    if not c.password_fb_enc:
        raise HTTPException(404, "El cliente no tiene contraseña de Facebook guardada")
    bitacora.registrar(db, user, "ver_password_fb", {"cliente_id": c.id})
    db.commit()
    return {"password": decrypt_value(c.password_fb_enc)}


@router.delete("/{cliente_id}")
def eliminar(cliente_id: int, confirmar_nombre: str, db: Session = Depends(get_db),
             user: Usuario = Depends(require_writer)):
    """Borrado definitivo con doble confirmación: hay que escribir el nombre exacto del cliente."""
    c = obtener_cliente(db, user, cliente_id)
    bloqueo.exigir_libre(db, c.id, hoy_mx())
    if confirmar_nombre != c.nombre:
        raise HTTPException(422, "El nombre escrito no coincide con el del cliente")
    bitacora.registrar(db, user, "borrar_cliente", {"cliente_id": c.id, "nombre": c.nombre, "cm_id": c.cm_id})
    db.delete(c)
    db.commit()
    return {"ok": True}


@router.post("/{cliente_id}/reasignar")
def reasignar(cliente_id: int, datos: ReasignarIn, db: Session = Depends(get_db),
              admin: Usuario = Depends(require_admin_write)):
    c = obtener_cliente(db, admin, cliente_id)
    if datos.cm_id is not None:
        cm = db.get(Usuario, datos.cm_id)
        if cm is None or cm.rol != "cm" or not cm.activo:
            raise HTTPException(422, "El CM destino no existe o está dado de baja")
    anterior = c.cm_id
    c.cm_id = datos.cm_id
    for a in db.scalars(select(ArchivoNoRenovado).where(ArchivoNoRenovado.cliente_id == c.id)):
        a.cm_id = datos.cm_id
    bitacora.registrar(db, admin, "reasignar_cliente", {"cliente_id": c.id, "de": anterior, "a": datos.cm_id})
    db.commit()
    return {"ok": True}
