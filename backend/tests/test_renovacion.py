import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import (ArchivoNoRenovado, Bitacora, Cliente, Notificacion, PaqueteCliente, Pago, Renovacion)

H = dt.date(2026, 10, 1)
D = dt.timedelta


@pytest.fixture(autouse=True)
def _hoy(hoy_fijo):
    hoy_fijo(H)


@pytest.fixture
def ctx(db, crear_usuario, fabrica, auth):
    ana = crear_usuario("ana.ruiz")
    c = fabrica.cliente(ana, "Cliente Ana")
    return dict(ana=ana, c=c, h=auth(ana))


# --------------------------------------------------------------------------- renovar
def test_renovar_mismo_paquete_abre_ciclo_nuevo_y_conserva_el_anterior(api, db, ctx, fabrica):
    p = fabrica.ciclo(ctx["c"], H + D(2), costo=1500, pagos=[(500, H)])
    r = api.post(f"/api/paquetes/{p.id}/renovar", headers=ctx["h"], json={})
    assert r.status_code == 200
    nuevo, ant = r.json()["nuevo"], r.json()["anterior"]
    assert nuevo["fecha_renovacion"] == str(H + D(32))                 # +30 días
    assert nuevo["fecha_inicio"] == str(H + D(2)) and float(nuevo["pagado"]) == 0
    assert nuevo["ciclo_anterior_id"] == p.id and nuevo["estado"] == "activo"
    assert ant["estado"] == "renovado" and ant["renovacion_decision"] == "si"
    assert float(ant["pagado"]) == 500 and float(ant["restante"]) == 1000          # la deuda se conserva
    rn = db.scalars(select(Renovacion)).one()
    assert (rn.costo_anterior, rn.costo_nuevo) == (Decimal(1500), Decimal(1500)) and rn.paquete_anterior_id == rn.paquete_nuevo_id


def test_renovar_cambiando_de_paquete_costo_y_fecha(api, db, ctx, fabrica):
    p = fabrica.ciclo(ctx["c"], H + D(2), costo=1500, paquete="Básico")
    r = api.post(f"/api/paquetes/{p.id}/renovar", headers=ctx["h"],
                 json={"paquete_id": 3, "costo": 4500, "fecha_renovacion": str(H + D(40))})
    assert r.status_code == 200
    assert r.json()["nuevo"]["paquete"] == "Élite" and float(r.json()["nuevo"]["costo"]) == 4500
    rn = db.scalars(select(Renovacion)).one()
    assert (rn.costo_anterior, rn.costo_nuevo, rn.paquete_nuevo_id) == (Decimal(1500), Decimal(4500), 3)


def test_renovar_exige_fecha_posterior_y_solo_ciclos_vigentes(api, ctx, fabrica):
    p = fabrica.ciclo(ctx["c"], H + D(2))
    assert api.post(f"/api/paquetes/{p.id}/renovar", headers=ctx["h"], json={"fecha_renovacion": str(H + D(2))}).status_code == 422
    assert api.post(f"/api/paquetes/{p.id}/renovar", headers=ctx["h"], json={}).status_code == 200
    assert api.post(f"/api/paquetes/{p.id}/renovar", headers=ctx["h"], json={}).status_code == 409   # ya renovado


def test_deuda_de_ciclo_renovado_sigue_admitiendo_pagos_y_prorroga(api, ctx, fabrica):
    p = fabrica.ciclo(ctx["c"], H + D(2), costo=1000)
    api.post(f"/api/paquetes/{p.id}/renovar", headers=ctx["h"], json={})
    assert api.post(f"/api/paquetes/{p.id}/pagos", headers=ctx["h"], json={"monto": 400}).status_code == 201
    assert api.put(f"/api/paquetes/{p.id}/prorroga", headers=ctx["h"], json={"hasta": str(H + D(7))}).status_code == 200


def test_renovar_marca_leidos_los_avisos_del_paquete(api, db, ctx, fabrica):
    from app.jobs import tareas
    p = fabrica.ciclo(ctx["c"], H + D(3))
    tareas.avisos_renovacion(db, H)
    assert db.scalar(select(func.count()).select_from(Notificacion).where(Notificacion.leida.is_(False))) == 1
    api.post(f"/api/paquetes/{p.id}/renovar", headers=ctx["h"], json={})
    assert db.scalar(select(func.count()).select_from(Notificacion).where(Notificacion.leida.is_(False))) == 0


# ----------------------------------------------------------------------- no renovar
def test_no_renovar_conservar_con_otros_paquetes_el_cliente_sigue_activo(api, db, ctx, fabrica):
    a, b = fabrica.ciclo(ctx["c"], H + D(2)), fabrica.ciclo(ctx["c"], H + D(20), paquete="Élite")
    r = api.post(f"/api/paquetes/{a.id}/no-renovar", headers=ctx["h"], json={"accion": "conservar"})
    assert r.json() == {"cliente_eliminado": False, "cliente_a_no_renovados": False}
    db.refresh(a), db.refresh(ctx["c"])
    assert a.estado == "archivado" and a.archivado_en and ctx["c"].estado == "activo"
    assert db.scalar(select(func.count()).select_from(ArchivoNoRenovado)) == 0


def test_no_renovar_ultimo_paquete_manda_al_cliente_a_no_renovados(api, db, ctx, fabrica):
    a = fabrica.ciclo(ctx["c"], H + D(2))
    r = api.post(f"/api/paquetes/{a.id}/no-renovar", headers=ctx["h"], json={"accion": "conservar"})
    assert r.json()["cliente_a_no_renovados"] is True
    db.refresh(ctx["c"])
    assert ctx["c"].estado == "no_renovado"
    assert db.scalars(select(ArchivoNoRenovado)).one().reingresado_en is None
    assert [c["nombre"] for c in api.get("/api/clientes?estado=no_renovado", headers=ctx["h"]).json()] == ["Cliente Ana"]
    assert api.get("/api/clientes", headers=ctx["h"]).json() == []


def test_cliente_con_ciclo_renovado_pero_sin_vigentes_tambien_pasa_a_no_renovados(api, db, ctx, fabrica):
    viejo = fabrica.ciclo(ctx["c"], H - D(5), estado="renovado", decision="si")
    nuevo = fabrica.ciclo(ctx["c"], H + D(25), anterior=viejo)
    api.post(f"/api/paquetes/{nuevo.id}/no-renovar", headers=ctx["h"], json={"accion": "conservar"})
    db.refresh(ctx["c"])
    assert ctx["c"].estado == "no_renovado"


def test_borrar_paquete_exige_nombre_exacto(api, db, ctx, fabrica):
    a, _ = fabrica.ciclo(ctx["c"], H + D(2), paquete="Estándar"), fabrica.ciclo(ctx["c"], H + D(20))
    url = f"/api/paquetes/{a.id}/no-renovar"
    for mal in (None, "estándar", "Estandar", "Básico"):
        assert api.post(url, headers=ctx["h"], json={"accion": "borrar", "confirmar_nombre": mal}).status_code == 422
    assert api.post(url, headers=ctx["h"], json={"accion": "borrar", "confirmar_nombre": "Estándar"}).status_code == 200
    db.refresh(a)
    assert a.estado == "eliminado"
    assert all(p["id"] != a.id for p in api.get(f"/api/clientes/{ctx['c'].id}", headers=ctx["h"]).json()["historial"])


def test_borrar_ultimo_paquete_pregunta_si_se_elimina_el_cliente(api, db, ctx, fabrica):
    a = fabrica.ciclo(ctx["c"], H + D(2))
    cuerpo = {"accion": "borrar", "confirmar_nombre": "Básico"}
    r = api.post(f"/api/paquetes/{a.id}/no-renovar", headers=ctx["h"], json=cuerpo)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ultimo_paquete"
    db.refresh(a)
    assert a.estado == "activo"                                                    # nada cambió
    r = api.post(f"/api/paquetes/{a.id}/no-renovar", headers=ctx["h"], json={**cuerpo, "eliminar_cliente": False})
    assert r.json()["cliente_a_no_renovados"] is True and db.get(Cliente, ctx["c"].id).estado == "no_renovado"


def test_borrar_ultimo_paquete_y_cliente_con_historial_de_ciclos(api, db, ctx, fabrica):
    """Regresión: la cadena de ciclos (FK a sí misma) no debe romper el borrado en cascada."""
    viejo = fabrica.ciclo(ctx["c"], H - D(5), estado="renovado", decision="si", pagos=[(100, H)])
    nuevo = fabrica.ciclo(ctx["c"], H + D(25), anterior=viejo)
    db.add(Renovacion(ciclo_anterior_id=viejo.id, ciclo_nuevo_id=nuevo.id, paquete_anterior_id=1, paquete_nuevo_id=1,
                      costo_anterior=1500, costo_nuevo=1500, fecha=H))
    db.flush()
    cid = ctx["c"].id
    r = api.post(f"/api/paquetes/{nuevo.id}/no-renovar", headers=ctx["h"],
                 json={"accion": "borrar", "confirmar_nombre": "Básico", "eliminar_cliente": True})
    assert r.json()["cliente_eliminado"] is True
    db.expire_all()
    assert db.get(Cliente, cid) is None
    assert db.scalar(select(func.count()).select_from(PaqueteCliente).where(PaqueteCliente.cliente_id == cid)) == 0
    assert db.scalar(select(func.count()).select_from(Pago)) == 0


# ------------------------------------------------------------------------- reingreso
def _no_renovado(db, fabrica, ctx, dias, con_historial=True):
    c = ctx["c"]
    c.estado = "no_renovado"
    p = fabrica.ciclo(c, H - D(dias + 1), estado="archivado", decision="no", costo=2500, paquete="Estándar",
                      pagos=[(2500, H - D(dias + 5))])
    p.archivado_en = dt.datetime.combine(H, dt.time(12), tzinfo=dt.timezone.utc) - D(dias)
    db.add(ArchivoNoRenovado(cliente_id=c.id, cm_id=c.cm_id, archivado_en=p.archivado_en))
    db.flush()
    return p


def test_reingreso_menos_de_2_meses_puede_continuar_el_paquete_anterior(api, db, ctx, fabrica):
    anterior = _no_renovado(db, fabrica, ctx, 20)
    info = api.get(f"/api/clientes/{ctx['c'].id}/reingreso-info", headers=ctx["h"]).json()
    assert info["forzar_nuevo"] is False
    r = api.post(f"/api/clientes/{ctx['c'].id}/reingreso", headers=ctx["h"],
                 json={"modo": "continuar", "fecha_renovacion": str(H + D(30))})
    assert r.status_code == 200 and r.json()["estado"] == "activo"
    nuevo = r.json()["paquetes"][0]
    assert nuevo["paquete"] == "Estándar" and float(nuevo["costo"]) == 2500 and nuevo["ciclo_anterior_id"] == anterior.id
    assert [h["id"] for h in r.json()["historial"]] == [anterior.id]              # historial conservado
    assert db.scalars(select(ArchivoNoRenovado)).one().reingresado_en is not None


def test_reingreso_menos_de_2_meses_paquete_nuevo_conserva_historial(api, db, ctx, fabrica):
    anterior = _no_renovado(db, fabrica, ctx, 59)
    r = api.post(f"/api/clientes/{ctx['c'].id}/reingreso", headers=ctx["h"],
                 json={"modo": "nuevo", "paquete_id": 3, "tipo_id": 2, "costo": 4500})
    assert r.status_code == 200
    assert r.json()["paquetes"][0]["paquete"] == "Élite" and len(r.json()["historial"]) == 1
    assert db.get(PaqueteCliente, anterior.id) is not None


def test_reingreso_2_meses_o_mas_fuerza_nuevo_y_borra_el_historial(api, db, ctx, fabrica):
    anterior = _no_renovado(db, fabrica, ctx, 62)
    assert api.get(f"/api/clientes/{ctx['c'].id}/reingreso-info", headers=ctx["h"]).json()["forzar_nuevo"] is True
    cid = ctx["c"].id
    assert api.post(f"/api/clientes/{cid}/reingreso", headers=ctx["h"],
                    json={"modo": "continuar", "fecha_renovacion": str(H + D(30))}).status_code == 422
    r = api.post(f"/api/clientes/{cid}/reingreso", headers=ctx["h"],
                 json={"modo": "nuevo", "paquete_id": 1, "tipo_id": 1, "costo": 1500})
    assert r.status_code == 200 and r.json()["historial"] == []
    db.expire_all()
    assert db.get(PaqueteCliente, anterior.id) is None
    assert db.scalar(select(func.count()).select_from(Pago)) == 0                  # sus pagos también se fueron
    assert db.scalars(select(Bitacora).where(Bitacora.accion == "reingreso")).one().detalle["historial_borrado"] is True


def test_reingreso_frontera_exacta_de_2_meses(api, db, ctx, fabrica, hoy_fijo):
    """El día que se cumplen 2 meses calendario ya se fuerza paquete nuevo; un día antes, no."""
    hoy_fijo(dt.date(2026, 10, 31))
    _no_renovado(db, fabrica, ctx, 0)
    a = db.scalars(select(ArchivoNoRenovado)).one()
    tz = dt.timezone(dt.timedelta(hours=-6))
    for archivado, forzar in ((dt.datetime(2026, 8, 31, 11, 0, tzinfo=tz), True),     # justo 2 meses antes (31 ago)
                              (dt.datetime(2026, 9, 1, 11, 0, tzinfo=tz), False)):    # 1 sep: aún no cumple
        a.archivado_en = archivado
        db.flush()
        info = api.get(f"/api/clientes/{ctx['c'].id}/reingreso-info", headers=ctx["h"]).json()
        assert info["forzar_nuevo"] is forzar, archivado


def test_reingreso_solo_aplica_a_clientes_en_no_renovados(api, ctx):
    assert api.post(f"/api/clientes/{ctx['c'].id}/reingreso", headers=ctx["h"],
                    json={"modo": "nuevo", "paquete_id": 1, "tipo_id": 1, "costo": 1}).status_code == 409


def test_cliente_en_no_renovados_no_admite_paquetes_ni_renovar(api, db, ctx, fabrica):
    _no_renovado(db, fabrica, ctx, 10)
    r = api.post(f"/api/clientes/{ctx['c'].id}/paquetes", headers=ctx["h"],
                 json={"paquete_id": 1, "tipo_id": 1, "costo": 100, "fecha_renovacion": str(H + D(30))})
    assert r.status_code == 409


# ------------------------------------------------------------------------------ purga
def test_purga_elimina_solo_a_los_de_3_meses_o_mas(api, db, ctx, fabrica, crear_usuario):
    from app.services.renovacion import purgar_no_renovados
    ahora = dt.datetime(2026, 10, 1, 12, tzinfo=dt.timezone(dt.timedelta(hours=-6)))
    ana = ctx["ana"]
    nombres = {}
    for dias, nombre in ((89, "Reciente"), (92, "Antiguo"), (200, "Muy antiguo")):
        c = fabrica.cliente(ana, nombre, estado="no_renovado")
        p = fabrica.ciclo(c, H - D(dias), estado="archivado", decision="no", pagos=[(100, H - D(dias))])
        db.add(ArchivoNoRenovado(cliente_id=c.id, cm_id=ana.id, archivado_en=ahora - D(dias)))
        nombres[nombre] = c.id
    activo = fabrica.cliente(ana, "Activo viejo")
    fabrica.ciclo(activo, H + D(5))
    db.flush()
    assert sorted(purgar_no_renovados(db, ahora)) == ["Antiguo", "Muy antiguo"]
    db.expire_all()
    assert db.get(Cliente, nombres["Reciente"]) is not None and db.get(Cliente, activo.id) is not None
    assert db.get(Cliente, nombres["Antiguo"]) is None
    assert db.scalar(select(func.count()).select_from(ArchivoNoRenovado)) == 1       # sin IntegrityError por el CASCADE
    assert db.scalars(select(Bitacora).where(Bitacora.accion == "purga_no_renovados")).all().__len__() == 2


def test_purga_frontera_de_3_meses_calendario(db, ctx, fabrica):
    from app.services.renovacion import purgar_no_renovados
    tz = dt.timezone(dt.timedelta(hours=-6))
    c = fabrica.cliente(ctx["ana"], "Frontera", estado="no_renovado")
    fabrica.ciclo(c, H, estado="archivado", decision="no")
    db.add(ArchivoNoRenovado(cliente_id=c.id, archivado_en=dt.datetime(2026, 7, 1, 12, tzinfo=tz)))
    db.flush()
    assert purgar_no_renovados(db, dt.datetime(2026, 9, 30, 23, tzinfo=tz)) == []          # falta un día
    assert purgar_no_renovados(db, dt.datetime(2026, 10, 1, 12, tzinfo=tz)) == ["Frontera"]


# ----------------------------------------------------------------- jobs y notificaciones
def test_job_renovaciones_avisa_en_R_menos_4_y_marca_vencidos(db, ctx, fabrica):
    from app.jobs import tareas
    lejos = fabrica.ciclo(ctx["c"], H + D(5))
    aviso = fabrica.ciclo(ctx["c"], H + D(4))
    hoy_ = fabrica.ciclo(ctx["c"], H)
    pasado = fabrica.ciclo(ctx["c"], H - D(3))
    ya_decidido = fabrica.ciclo(ctx["c"], H, decision="no")
    assert tareas.avisos_renovacion(db, H) == {"avisos": 1, "marcados_vencidos": 2}
    for p in (lejos, aviso, hoy_, pasado, ya_decidido):
        db.refresh(p)
    assert [p.estado for p in (lejos, aviso, hoy_, pasado, ya_decidido)] == ["activo", "activo", "vencido", "vencido", "activo"]
    tipos = sorted(n.tipo for n in db.scalars(select(Notificacion)))
    assert tipos == ["paquete_vencido", "paquete_vencido", "renovacion_3d"]


def test_ejemplo_renueva_10_nov_aviso_6_nov(db, ctx, fabrica):
    from app.jobs import tareas
    fabrica.ciclo(ctx["c"], dt.date(2026, 11, 10))
    assert tareas.avisos_renovacion(db, dt.date(2026, 11, 5))["avisos"] == 0
    assert tareas.avisos_renovacion(db, dt.date(2026, 11, 6))["avisos"] == 1


def test_jobs_son_idempotentes_no_duplican_notificaciones(db, ctx, fabrica):
    from app.jobs import tareas
    fabrica.ciclo(ctx["c"], H + D(2))
    fabrica.ciclo(ctx["c"], H - D(1))
    fabrica.ciclo(ctx["c"], H - D(30), estado="vencido", pagos=[(10, H)], prorroga=(H - D(20), H - D(5)))
    for _ in range(3):
        tareas.avisos_renovacion(db, H)
        tareas.avisos_prorroga(db, H)
    assert db.scalar(select(func.count()).select_from(Notificacion)) == 3


def test_notificaciones_van_al_cm_y_si_esta_por_reasignar_a_los_admin(db, ctx, fabrica, crear_usuario):
    from app.jobs import tareas
    adm1, adm2 = crear_usuario("admin.uno", rol="admin"), crear_usuario("admin.dos", rol="admin", solo_lectura=True)
    crear_usuario("admin.baja", rol="admin", activo=False)
    huerfano = fabrica.cliente(None, "Sin CM")
    fabrica.ciclo(huerfano, H + D(1), por=adm1)
    fabrica.ciclo(ctx["c"], H + D(1))
    tareas.avisos_renovacion(db, H)
    dest = sorted(n.usuario_id for n in db.scalars(select(Notificacion)))
    assert dest == sorted([ctx["ana"].id, adm1.id, adm2.id])


def test_aviso_prorroga_3_dias_antes_y_vencida_con_pregunta(db, ctx, fabrica):
    from app.jobs import tareas
    en3 = fabrica.ciclo(ctx["c"], H - D(10), estado="vencido", prorroga=(H - D(12), H + D(3)))
    en4 = fabrica.ciclo(ctx["c"], H - D(10), estado="vencido", prorroga=(H - D(11), H + D(4)))
    venc = fabrica.ciclo(ctx["c"], H - D(30), estado="vencido", prorroga=(H - D(15), H - D(1)))
    pagada = fabrica.ciclo(ctx["c"], H - D(30), estado="vencido", pagos=[(1500, H)], prorroga=(H - D(15), H - D(1)))
    assert tareas.avisos_prorroga(db, H) == {"avisos_prorroga": 1, "prorrogas_vencidas": 1}
    notas = {n.paquete_id: n for n in db.scalars(select(Notificacion))}
    assert set(notas) == {en3.id, venc.id}
    assert notas[en3.id].tipo == "prorroga_3d" and not notas[en3.id].requiere_respuesta
    assert notas[venc.id].tipo == "prorroga_vencida" and notas[venc.id].requiere_respuesta


def test_responder_prorroga_vencida_si_captura_pago_no_genera_recordatorio(api, db, ctx, fabrica):
    from app.jobs import tareas
    a = fabrica.ciclo(ctx["c"], H - D(30), estado="vencido", costo=1000, prorroga=(H - D(15), H - D(1)))
    b = fabrica.ciclo(ctx["c"], H - D(30), estado="vencido", costo=1000, prorroga=(H - D(15), H - D(1)))
    tareas.avisos_prorroga(db, H)
    lista = api.get("/api/notificaciones", headers=ctx["h"]).json()
    assert lista["no_leidas"] == 2 and lista["preguntas_pendientes"] == 2
    na = next(n for n in lista["items"] if n["paquete_id"] == a.id)
    nb = next(n for n in lista["items"] if n["paquete_id"] == b.id)
    assert api.post(f"/api/notificaciones/{na['id']}/responder", headers=ctx["h"], json={"pago": "si"}).status_code == 422
    r = api.post(f"/api/notificaciones/{na['id']}/responder", headers=ctx["h"], json={"pago": "si", "monto": 1000})
    assert r.status_code == 200 and float(r.json()["paquete"]["restante"]) == 0
    assert r.json()["paquete"]["semaforo"] == "rojo"      # pagó, pero sigue vencido sin decisión de renovar
    r = api.post(f"/api/notificaciones/{nb['id']}/responder", headers=ctx["h"], json={"pago": "no"})
    assert r.json()["recordatorio"]["wa_url"].startswith("https://wa.me/52") and "1,000.00" in r.json()["recordatorio"]["texto"]
    assert api.post(f"/api/notificaciones/{nb['id']}/responder", headers=ctx["h"], json={"pago": "no"}).status_code == 409
    assert api.get("/api/notificaciones", headers=ctx["h"]).json()["preguntas_pendientes"] == 0


def test_cm_solo_ve_y_responde_sus_notificaciones(api, db, ctx, fabrica, crear_usuario, auth):
    from app.jobs import tareas
    fabrica.ciclo(ctx["c"], H + D(1))
    tareas.avisos_renovacion(db, H)
    beto = auth(crear_usuario("beto.luna"))
    assert api.get("/api/notificaciones", headers=beto).json()["items"] == []
    nid = api.get("/api/notificaciones", headers=ctx["h"]).json()["items"][0]["id"]
    assert api.post(f"/api/notificaciones/{nid}/leer", headers=beto).status_code == 404
    assert api.post(f"/api/notificaciones/{nid}/leer", headers=ctx["h"]).json()["leida"] is True
    assert api.get("/api/notificaciones?solo_no_leidas=true", headers=ctx["h"]).json()["no_leidas"] == 0


def test_endpoint_de_jobs_exige_secreto(api, db, monkeypatch):
    from contextlib import contextmanager

    from app.config import get_settings
    from app.jobs import tareas

    class _S:
        def __enter__(self): return db
        def __exit__(self, *a): return False
    monkeypatch.setattr(tareas, "get_sessionmaker", lambda: (lambda: _S()))
    assert api.post("/api/jobs/run/renovaciones").status_code == 401
    assert api.post("/api/jobs/run/renovaciones", headers={"X-Jobs-Secret": "mal"}).status_code == 401
    ok = api.post("/api/jobs/run/renovaciones", headers={"X-Jobs-Secret": get_settings().jobs_secret})
    assert ok.status_code == 200 and ok.json()["resultado"] == {"avisos": 0, "marcados_vencidos": 0}
    assert api.post("/api/jobs/run/inexistente", headers={"X-Jobs-Secret": get_settings().jobs_secret}).status_code == 404


# ----------------------------------------------------------------------------- tablero
def test_tablero_cuatro_columnas(api, db, ctx, fabrica, crear_usuario, auth):
    c = ctx["c"]
    por_vencer = fabrica.ciclo(c, H + D(3))                                                     # 1ra quincena? H=1 oct -> día 4
    vencido = fabrica.ciclo(c, H - D(2), estado="vencido")                                      # 29 sep: arrastrado
    sin_pago = fabrica.ciclo(c, H + D(1), estado="renovado", decision="si", pagos=[(100, H)])
    completo = fabrica.ciclo(c, H + D(2), estado="renovado", decision="si", pagos=[(1500, H)])
    en_plazo = fabrica.ciclo(c, H + D(10))
    fuera = fabrica.ciclo(c, H + D(20))                                                         # 2da quincena
    arch = fabrica.ciclo(c, H + D(2), estado="archivado", decision="no")
    otro = fabrica.cliente(crear_usuario("beto.luna"), "Ajeno")
    fabrica.ciclo(otro, H + D(2))
    r = api.get("/api/renovaciones/tablero?anio=2026&mes=10&quincena=1", headers=ctx["h"]).json()
    ids = {k: [t["id"] for t in v] for k, v in r["columnas"].items()}
    assert ids == {"por_vencer": [por_vencer.id], "vencidos": [vencido.id], "renovados_sin_pago": [sin_pago.id],
                   "completos": [completo.id]}
    assert r["en_plazo"] == 1                                       # en_plazo; "fuera" no cuenta en esta quincena
    assert r["columnas"]["vencidos"][0]["arrastrado"] is True and r["columnas"]["por_vencer"][0]["arrastrado"] is False
    assert r["columnas"]["por_vencer"][0]["cliente_nombre"] == "Cliente Ana"
    # 2da quincena: por_vencer/completos del periodo; lo arrastrado sigue visible
    r2 = api.get("/api/renovaciones/tablero?anio=2026&mes=10&quincena=2", headers=ctx["h"]).json()
    ids2 = {k: [t["id"] for t in v] for k, v in r2["columnas"].items()}
    assert vencido.id in ids2["vencidos"] and sin_pago.id in ids2["renovados_sin_pago"] and r2["en_plazo"] == 1
    # el admin puede filtrar por CM; un CM no ve ajenos aunque lo pida
    adm = auth(crear_usuario("admin.demo", rol="admin"))
    todos = api.get("/api/renovaciones/tablero?anio=2026&mes=10&quincena=1", headers=adm).json()
    assert sum(len(v) for v in todos["columnas"].values()) == 5 and todos["en_plazo"] == 1
    solo = api.get(f"/api/renovaciones/tablero?anio=2026&mes=10&quincena=1&cm_id={ctx['ana'].id}", headers=adm).json()
    assert sum(len(v) for v in solo["columnas"].values()) == 4
    h = ctx["h"]
    assert "Ajeno" not in api.get(f"/api/renovaciones/tablero?anio=2026&mes=10&quincena=1&cm_id={otro.cm_id}", headers=h).text


def test_cambiar_de_paquete_reinicia_el_contador_de_renovaciones(api, db, ctx, fabrica):
    p = fabrica.ciclo(ctx["c"], H + D(2), paquete="Básico")
    h = ctx["h"]
    n1 = api.post(f"/api/paquetes/{p.id}/renovar", headers=h, json={}).json()["nuevo"]
    n2 = api.post(f"/api/paquetes/{n1['id']}/renovar", headers=h, json={}).json()["nuevo"]
    assert (n1["veces_renovado"], n2["veces_renovado"]) == (1, 2)
    # renueva con OTRO paquete: cuenta en 0 y cambian nombre, tipo y costo
    n3 = api.post(f"/api/paquetes/{n2['id']}/renovar", headers=h,
                  json={"paquete_id": 3, "tipo_id": 2, "costo": 4500}).json()["nuevo"]
    assert (n3["veces_renovado"], n3["paquete"], n3["tipo"], float(n3["costo"])) == (0, "Élite", "Dinamita", 4500)
    n4 = api.post(f"/api/paquetes/{n3['id']}/renovar", headers=h, json={}).json()["nuevo"]
    assert n4["veces_renovado"] == 1                                   # empieza a contar de nuevo con el paquete nuevo
    # el historial de ciclos anteriores sigue ahí
    d = api.get(f"/api/paquetes/{n4['id']}", headers=h).json()
    assert d["veces_renovado"] == 1 and len(d["ciclos"]) == 5
