import datetime as dt
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.database import get_db
from app.dates import ahora
from app.deps import get_current_user, require_writer
from app.models import Notificacion, Usuario
from app.routers.paquetes import generar_recordatorio, recordatorio_out
from app.services import ciclos
from app.services import pagos as pagos_svc
from app.services.scope import obtener_paquete

router = APIRouter(prefix="/api/notificaciones", tags=["notificaciones"])


class RespuestaIn(BaseModel):
    pago: str = Field(pattern="^(si|no)$")
    monto: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    fecha: dt.date | None = None


def _out(n: Notificacion) -> dict:
    return {"id": n.id, "tipo": n.tipo, "mensaje": n.mensaje, "cliente_id": n.cliente_id, "paquete_id": n.paquete_id,
            "requiere_respuesta": n.requiere_respuesta, "respuesta": n.respuesta, "respondida_en": n.respondida_en,
            "leida": n.leida, "creado_en": n.creado_en}


def _propia(db: Session, user: Usuario, nid: int) -> Notificacion:
    n = db.get(Notificacion, nid)
    if n is None or n.usuario_id != user.id:
        raise HTTPException(404, "Notificación no encontrada")
    return n


@router.get("")
def listar(solo_no_leidas: bool = False, limite: int = 50, db: Session = Depends(get_db),
           user: Usuario = Depends(get_current_user)):
    q = select(Notificacion).where(Notificacion.usuario_id == user.id)
    if solo_no_leidas:
        q = q.where(Notificacion.leida.is_(False))
    filas = db.scalars(q.order_by(Notificacion.id.desc()).limit(min(limite, 200))).all()
    no_leidas = db.scalar(select(func.count()).select_from(Notificacion).where(
        Notificacion.usuario_id == user.id, Notificacion.leida.is_(False)))
    pendientes = db.scalar(select(func.count()).select_from(Notificacion).where(
        Notificacion.usuario_id == user.id, Notificacion.requiere_respuesta, Notificacion.respondida_en.is_(None)))
    return {"no_leidas": no_leidas, "preguntas_pendientes": pendientes, "items": [_out(n) for n in filas]}


@router.post("/leer-todas")
def leer_todas(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    db.execute(update(Notificacion).where(Notificacion.usuario_id == user.id, Notificacion.leida.is_(False),
                                          Notificacion.requiere_respuesta.is_(False)).values(leida=True))
    db.commit()
    return {"ok": True}


@router.post("/{nid}/leer")
def leer(nid: int, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    n = _propia(db, user, nid)
    n.leida = True
    db.commit()
    return _out(n)


@router.post("/{nid}/responder")
def responder(nid: int, datos: RespuestaIn, db: Session = Depends(get_db), user: Usuario = Depends(require_writer)):
    """Pregunta '¿El cliente pagó?' de una prórroga vencida.
    Sí -> captura el pago (monto). No -> genera el recordatorio para el cliente (texto + wa.me)."""
    n = _propia(db, user, nid)
    if not n.requiere_respuesta:
        raise HTTPException(409, "Esta notificación no requiere respuesta")
    if n.respondida_en is not None:
        raise HTTPException(409, "Esta pregunta ya fue respondida")
    p = obtener_paquete(db, user, n.paquete_id)      # 404 si el cliente ya no es de su cartera
    resultado: dict = {}
    if datos.pago == "si":
        if datos.monto is None:
            raise HTTPException(422, "Indica el monto que pagó el cliente")
        pagos_svc.registrar_pago(db, user, p, datos.monto, datos.fecha, "Pago tras prórroga vencida")
        db.refresh(p)
        resultado["paquete"] = ciclos.paquete_out(p, ahora().date())
    else:
        if p.costo - ciclos.pagado_hasta(p) <= 0:
            raise HTTPException(422, "El paquete ya no tiene saldo pendiente")
        r = generar_recordatorio(db, p, p.cliente.cm_id)
        resultado["recordatorio"] = recordatorio_out(r, p.cliente.telefono)
    n.respuesta, n.respondida_en, n.leida = datos.pago, ahora(), True
    db.commit()
    return {"notificacion": _out(n), **resultado}
