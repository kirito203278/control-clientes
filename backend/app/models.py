"""Modelos ORM. Espejo de migrations/sql/001_init.sql (esa es la fuente de verdad
del esquema; los CHECK y triggers viven allá)."""
import datetime as dt
from decimal import Decimal

from sqlalchemy import (Boolean, Date, DateTime, ForeignKey, Integer, Numeric, Text, func)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _ts():
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(Text)
    username: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    rol: Mapped[str] = mapped_column(Text)
    solo_lectura: Mapped[bool] = mapped_column(Boolean, default=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    primer_ingreso: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[dt.datetime] = _ts()


class CatalogoPaquete(Base):
    __tablename__ = "catalogo_paquetes"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(Text, unique=True)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class CatalogoTipo(Base):
    __tablename__ = "catalogo_tipos"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(Text, unique=True)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Cliente(Base):
    __tablename__ = "clientes"
    id: Mapped[int] = mapped_column(primary_key=True)
    cm_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))  # NULL = por reasignar
    nombre: Mapped[str] = mapped_column(Text)
    correo_fb_enc: Mapped[str | None] = mapped_column(Text)
    password_fb_enc: Mapped[str | None] = mapped_column(Text)
    correo_contacto: Mapped[str | None] = mapped_column(Text)
    telefono: Mapped[str | None] = mapped_column(Text)
    observaciones: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(Text, default="activo")
    creado_en: Mapped[dt.datetime] = _ts()
    actualizado_en: Mapped[dt.datetime] = _ts()

    paquetes: Mapped[list["PaqueteCliente"]] = relationship(back_populates="cliente", cascade="all, delete-orphan", passive_deletes=True)


class PaqueteCliente(Base):
    """Un CICLO de un paquete de un cliente."""
    __tablename__ = "paquetes_cliente"
    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    paquete_id: Mapped[int] = mapped_column(ForeignKey("catalogo_paquetes.id"))
    tipo_id: Mapped[int] = mapped_column(ForeignKey("catalogo_tipos.id"))
    costo: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    fecha_inicio: Mapped[dt.date] = mapped_column(Date)
    fecha_renovacion: Mapped[dt.date] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(Text, default="activo")
    renovacion_decision: Mapped[str] = mapped_column(Text, default="pendiente")
    renovacion_pagada: Mapped[bool] = mapped_column(Boolean, default=False)
    prorroga_hasta: Mapped[dt.date | None] = mapped_column(Date)
    prorroga_registrada_en: Mapped[dt.date | None] = mapped_column(Date)
    ciclo_anterior_id: Mapped[int | None] = mapped_column(ForeignKey("paquetes_cliente.id"))
    archivado_en: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[dt.datetime] = _ts()

    cliente: Mapped[Cliente] = relationship(back_populates="paquetes")
    paquete: Mapped[CatalogoPaquete] = relationship()
    tipo: Mapped[CatalogoTipo] = relationship()
    pagos: Mapped[list["Pago"]] = relationship(back_populates="paquete_cliente", cascade="all, delete-orphan", passive_deletes=True)

    @property
    def pagado(self) -> Decimal:
        return sum((p.monto for p in self.pagos), Decimal("0"))

    @property
    def restante(self) -> Decimal:
        return self.costo - self.pagado


class Pago(Base):
    __tablename__ = "pagos"
    id: Mapped[int] = mapped_column(primary_key=True)
    paquete_id: Mapped[int] = mapped_column(ForeignKey("paquetes_cliente.id", ondelete="CASCADE"))
    monto: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    fecha: Mapped[dt.date] = mapped_column(Date)
    nota: Mapped[str | None] = mapped_column(Text)
    registrado_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[dt.datetime] = _ts()

    paquete_cliente: Mapped[PaqueteCliente] = relationship(back_populates="pagos")


class Renovacion(Base):
    __tablename__ = "renovaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    ciclo_anterior_id: Mapped[int] = mapped_column(ForeignKey("paquetes_cliente.id", ondelete="CASCADE"))
    ciclo_nuevo_id: Mapped[int] = mapped_column(ForeignKey("paquetes_cliente.id", ondelete="CASCADE"))
    paquete_anterior_id: Mapped[int] = mapped_column(ForeignKey("catalogo_paquetes.id"))
    paquete_nuevo_id: Mapped[int] = mapped_column(ForeignKey("catalogo_paquetes.id"))
    costo_anterior: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    costo_nuevo: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    fecha: Mapped[dt.date] = mapped_column(Date)
    registrado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[dt.datetime] = _ts()


class ArchivoNoRenovado(Base):
    __tablename__ = "archivo_no_renovados"
    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    cm_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    motivo: Mapped[str | None] = mapped_column(Text)
    archivado_en: Mapped[dt.datetime] = _ts()
    reingresado_en: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class RecordatorioCliente(Base):
    __tablename__ = "recordatorios_cliente"
    id: Mapped[int] = mapped_column(primary_key=True)
    paquete_id: Mapped[int] = mapped_column(ForeignKey("paquetes_cliente.id", ondelete="CASCADE"))
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    cm_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    telefono_destino: Mapped[str | None] = mapped_column(Text)
    texto: Mapped[str] = mapped_column(Text)
    generado_en: Mapped[dt.datetime] = _ts()
    enviado_en: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class Notificacion(Base):
    __tablename__ = "notificaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    tipo: Mapped[str] = mapped_column(Text)
    mensaje: Mapped[str] = mapped_column(Text)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    paquete_id: Mapped[int | None] = mapped_column(ForeignKey("paquetes_cliente.id", ondelete="CASCADE"))
    requiere_respuesta: Mapped[bool] = mapped_column(Boolean, default=False)
    respuesta: Mapped[str | None] = mapped_column(Text)
    respondida_en: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    leida: Mapped[bool] = mapped_column(Boolean, default=False)
    dedupe_key: Mapped[str | None] = mapped_column(Text, unique=True)
    creado_en: Mapped[dt.datetime] = _ts()


class Bitacora(Base):
    __tablename__ = "bitacora"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    accion: Mapped[str] = mapped_column(Text)
    detalle: Mapped[dict | None] = mapped_column(JSONB)
    creado_en: Mapped[dt.datetime] = _ts()


class JobEjecucion(Base):
    __tablename__ = "jobs_ejecuciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(Text)
    origen: Mapped[str] = mapped_column(Text)
    ejecutado_en: Mapped[dt.datetime] = _ts()
    resultado: Mapped[dict | None] = mapped_column(JSONB)
