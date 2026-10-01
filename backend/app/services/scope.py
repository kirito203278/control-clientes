from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.models import Cliente, Pago, PaqueteCliente, Usuario


def clientes_q(user: Usuario) -> Select:
    q = select(Cliente)
    if user.rol == "cm":
        q = q.where(Cliente.cm_id == user.id)
    return q


def paquetes_q(user: Usuario) -> Select:
    q = select(PaqueteCliente).join(Cliente, Cliente.id == PaqueteCliente.cliente_id)
    if user.rol == "cm":
        q = q.where(Cliente.cm_id == user.id)
    return q


def obtener_cliente(db: Session, user: Usuario, cliente_id: int) -> Cliente:
    c = db.scalars(clientes_q(user).where(Cliente.id == cliente_id)).first()
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente no encontrado")
    return c


def obtener_paquete(db: Session, user: Usuario, paquete_id: int) -> PaqueteCliente:
    p = db.scalars(paquetes_q(user).where(PaqueteCliente.id == paquete_id)
                   .options(selectinload(PaqueteCliente.pagos))).first()
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paquete no encontrado")
    return p


def obtener_pago(db: Session, user: Usuario, pago_id: int) -> Pago:
    pago = db.get(Pago, pago_id)
    if pago is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pago no encontrado")
    obtener_paquete(db, user, pago.paquete_id)
    return pago
