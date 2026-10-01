"""Datos de ejemplo (FICTICIOS) para desarrollo y pruebas.

Las fechas son relativas a "hoy" para que cada escenario (por vencer, vencido,
prórroga por vencer, prórroga vencida, No renovados antiguos...) siga vigente
cuando se vuelva a sembrar. Las contraseñas se generan al azar y se escriben
SOLO en backend/seed_credentials.txt (ignorado por git), nunca en consola.

    python -m app.seed            # falla si ya hay usuarios
    FORCE_SEED=true python -m app.seed   # (solo dev) vacía y vuelve a sembrar
"""
import datetime as dt
import os
import re
import unicodedata
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dates import ahora, hoy
from app.database import get_sessionmaker
from app.models import (ArchivoNoRenovado, CatalogoPaquete, CatalogoTipo, Cliente, PaqueteCliente, Pago,
                        Renovacion, Usuario)
from app.security.crypto import encrypt_value
from app.security.passwords import generate_secure_password, hash_password

CREDENCIALES_PATH = Path(__file__).resolve().parent.parent / "seed_credentials.txt"

USUARIOS = [
    # (nombre, username, rol, solo_lectura)
    ("Admin Demo", "admin.demo", "admin", False),
    ("Lectura Demo", "lectura.demo", "admin", True),
    ("Ana Ruiz", "ana.ruiz", "cm", False),
    ("Beto Luna", "beto.luna", "cm", False),
    ("Carla Soto", "carla.soto", "cm", False),
]


def _slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", ".", t.lower()).strip(".")


def vaciar(db: Session) -> None:
    db.execute(text(
        "TRUNCATE notificaciones, bitacora, jobs_ejecuciones, recordatorios_cliente, renovaciones, pagos, "
        "archivo_no_renovados, paquetes_cliente, clientes, usuarios RESTART IDENTITY CASCADE"
    ))


def sembrar(db: Session, credenciales_path: Path | None = CREDENCIALES_PATH) -> dict:
    if db.scalar(select(Usuario.id).limit(1)) is not None:
        raise RuntimeError("Ya hay usuarios en la base. Usa FORCE_SEED=true solo en desarrollo.")

    H = hoy()
    ts_ahora = ahora()
    ciclo_dias = get_settings().ciclo_dias
    paq = {p.nombre: p.id for p in db.scalars(select(CatalogoPaquete))}
    tipo = {t.nombre: t.id for t in db.scalars(select(CatalogoTipo))}

    # ---- usuarios
    lineas, users = [], {}
    for nombre, username, rol, ro in USUARIOS:
        pwd = generate_secure_password()
        u = Usuario(nombre=nombre, username=username, password_hash=hash_password(pwd),
                    rol=rol, solo_lectura=ro, primer_ingreso=False)
        db.add(u)
        users[username] = u
        lineas.append(f"{username}\t{rol}{' (solo lectura)' if ro else ''}\t{pwd}")
    db.flush()
    admin, ana, beto, carla = (users[k] for k in ("admin.demo", "ana.ruiz", "beto.luna", "carla.soto"))

    # ---- helpers
    n_cliente = 0

    def cliente(cm: Usuario | None, nombre: str, estado: str = "activo", obs: str | None = None) -> Cliente:
        nonlocal n_cliente
        n_cliente += 1
        c = Cliente(cm_id=cm.id if cm else None, nombre=nombre, estado=estado, observaciones=obs,
                    correo_fb_enc=encrypt_value(f"{_slug(nombre)}@fb.ejemplo.test"),
                    password_fb_enc=encrypt_value(f"FbDemo-{n_cliente:02d}!x"),
                    correo_contacto=f"contacto@{_slug(nombre)}.ejemplo.test",
                    telefono=f"55550{n_cliente:05d}")
        db.add(c)
        db.flush()
        return c

    def ciclo(c: Cliente, paquete: str, tp: str, costo: int, renov: int, *, estado="activo", decision="pendiente",
              pagos: list[tuple[int, int]] = (), prorroga: tuple[int, int] | None = None,
              anterior: PaqueteCliente | None = None, por: Usuario | None = None) -> PaqueteCliente:
        """renov/pagos/prorroga en días relativos a hoy (negativo = pasado)."""
        f_ren = H + dt.timedelta(days=renov)
        p = PaqueteCliente(
            cliente_id=c.id, paquete_id=paq[paquete], tipo_id=tipo[tp], costo=Decimal(costo),
            fecha_inicio=f_ren - dt.timedelta(days=ciclo_dias), fecha_renovacion=f_ren, estado=estado,
            renovacion_decision=decision, ciclo_anterior_id=anterior.id if anterior else None,
            prorroga_registrada_en=H + dt.timedelta(days=prorroga[0]) if prorroga else None,
            prorroga_hasta=H + dt.timedelta(days=prorroga[1]) if prorroga else None,
        )
        db.add(p)
        db.flush()
        quien = por or db.get(Usuario, c.cm_id) or admin
        total = 0
        for monto, dias in pagos:
            db.add(Pago(paquete_id=p.id, monto=Decimal(monto), fecha=H + dt.timedelta(days=dias),
                        registrado_por=quien.id))
            total += monto
        p.renovacion_pagada = total >= costo
        return p

    def no_renovado(c: Cliente, dias: int, paquete: str, tp: str, costo: int) -> None:
        c.estado = "no_renovado"
        p = ciclo(c, paquete, tp, costo, -dias - 1, estado="archivado", decision="no",
                  pagos=[(costo, -dias - 10)])
        p.archivado_en = ts_ahora - dt.timedelta(days=dias)
        db.add(ArchivoNoRenovado(cliente_id=c.id, cm_id=c.cm_id, motivo="Decidió no renovar",
                                 archivado_en=ts_ahora - dt.timedelta(days=dias)))

    # ---- Ana
    ciclo(cliente(ana, "Panadería La Espiga"), "Básico", "Normal", 1500, 12)
    mv = cliente(ana, "Dra. Mariana Vélez", obs="Prefiere contacto por WhatsApp por las tardes.")
    ciclo(mv, "Estándar", "Normal", 2500, 4)                                   # aviso "¿renueva?" hoy (R-4)
    ciclo(mv, "Campaña", "Campaña", 4000, 20, pagos=[(1000, -3)])              # 2º paquete, otra quincena
    ciclo(cliente(ana, "Taller Hermanos Ríos"), "Élite", "Dinamita", 4500, 2,
          decision="si", pagos=[(4500, -1)])                                   # verde
    ciclo(cliente(ana, "Estética Bella Vista"), "Básico", "Fantasma", 1200, 1,
          decision="si", pagos=[(600, -2)])                                    # amarillo
    # ---- Beto
    ciclo(cliente(beto, "Gimnasio FuerzaMX"), "Estándar", "Normal", 2500, -2, estado="vencido")   # rojo
    ciclo(cliente(beto, "Café Tlalli"), "Básico", "Normal", 1500, -6, estado="vencido",
          pagos=[(700, -5)], prorroga=(-4, 3))                                 # prórroga vence en 3 días
    pl = cliente(beto, "Papelería El Lápiz")
    viejo = ciclo(pl, "Estándar", "Normal", 2500, -10, estado="renovado", decision="si",
                  pagos=[(1500, -12)], prorroga=(-14, -3))                     # prórroga vencida, debe 1000
    nuevo = ciclo(pl, "Élite", "Normal", 4500, 20, anterior=viejo)             # subió de nivel
    db.add(Renovacion(ciclo_anterior_id=viejo.id, ciclo_nuevo_id=nuevo.id, paquete_anterior_id=paq["Estándar"],
                      paquete_nuevo_id=paq["Élite"], costo_anterior=Decimal(2500), costo_nuevo=Decimal(4500),
                      fecha=H - dt.timedelta(days=10), registrado_por=beto.id))
    ciclo(cliente(beto, "Constructora Peña"), "Campaña", "Campaña", 6000, 9, pagos=[(3000, -2)])
    # ---- Carla
    ciclo(cliente(carla, "Florería Jazmín"), "Básico", "Normal", 1500, 15, pagos=[(1500, -4)])
    ciclo(cliente(carla, "Despacho Contable Orozco"), "Élite", "Normal", 4500, 25)
    ciclo(cliente(carla, "Hotel Casa Azul"), "Estándar", "Dinamita", 2500, 6, pagos=[(1000, -1)])
    # ---- No renovados (distintas antigüedades para probar reingreso y purga)
    no_renovado(cliente(carla, "Veterinaria PatiTas"), 20, "Estándar", "Dinamita", 2500)        # <2 meses
    no_renovado(cliente(beto, "Abarrotes Doña Lucha"), 70, "Básico", "Normal", 1500)            # >=2 meses
    no_renovado(cliente(ana, "Refaccionaria Del Valle"), 95, "Básico", "Normal", 1500)          # >=3 meses: purga
    # ---- Por reasignar
    ciclo(cliente(None, "Escuela de Baile Ritmo"), "Básico", "Normal", 1500, 7, por=admin)

    db.commit()
    if credenciales_path:
        credenciales_path.write_text(
            "# Credenciales de prueba generadas por el seed (ignorado por git)\n# usuario\trol\tcontraseña\n"
            + "\n".join(lineas) + "\n", encoding="utf-8")
        os.chmod(credenciales_path, 0o600)
    return {"usuarios": len(USUARIOS), "clientes": n_cliente}


if __name__ == "__main__":
    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        if os.getenv("FORCE_SEED", "").lower() == "true":
            vaciar(db)
            db.commit()
        resumen = sembrar(db)
    print(f"[seed] {resumen['usuarios']} usuarios y {resumen['clientes']} clientes de ejemplo. "
          f"Credenciales en {CREDENCIALES_PATH}")
