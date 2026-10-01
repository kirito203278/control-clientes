# ESTADO — Control de clientes INNquietus

Referencia de solo lectura: `~/Documentos/referencia/sistema-campanas-master` (no modificar, no copiar entero).

## Fases
- [x] Fase 0 — Diseño: `docs/FASE0_esquema.sql`, `docs/FASE0_endpoints.md`. Respuestas recibidas (ver abajo); falta confirmar la línea de tiempo del ciclo.
- [ ] Fase 1 — BD, migraciones, seed, Docker, `.env`
- [ ] Fase 2 — Auth, roles, equipo, reasignación/baja
- [ ] Fase 3 — Panel CM
- [ ] Fase 4 — Renovación, No renovados, notificaciones, jobs
- [ ] Fase 5 — Ingresos, recordatorios WhatsApp (SIN importador: la cartera arranca de cero)
- [ ] Fase 6 — Reportes PDF/Excel + pruebas
- [ ] Fase 7 — Producción (Render + Neon, cron-job.org, UptimeRobot)

## Decisiones (propuestas, pendientes de confirmar salvo indicación)
- Cada fila de `paquetes_cliente` = un CICLO; renovar crea fila nueva (`ciclo_anterior_id`). Pagos cuelgan del ciclo.
- Estado "por vencer" se calcula, no se guarda. `renovacion_pagada` la mantiene el servidor (pagado >= costo).
- `eliminado` = borrado lógico del paquete (se conservan pagos para reportes históricos).
- `clientes.cm_id NULL` = "Clientes por reasignar".
- `notificaciones.dedupe_key UNIQUE` (el proyecto anterior duplicó avisos al correr el job varias veces).
- `archivo_no_renovados` con ON DELETE CASCADE (bug de la purga en el proyecto anterior).
- Reutilizado de la referencia: AES-GCM, JWT 12 h, rate limit 5/15 min en memoria, `X-Jobs-Secret`, Dockerfile 2 etapas, tokens CSS y `branding.py`. Claves nuevas.

## Decisiones confirmadas por el usuario
- Ciclo = 30 días fijos. Al renovar, nueva fecha = anterior + 30 días.
- El ciclo se cobra en cada renovación. Tolerancia de pago: 3 días; si después sigue debiendo, el CM debe registrar prórroga (15 días naturales desde que se registra; una por ciclo).
- Aviso "¿renueva?" 3 días antes de la fecha límite (= un día antes de la renovación). Pendiente confirmar si eso es R-4 o R-3.
- Si renueva: ventana para conservar los mismos paquetes u otros; deudas/paquetes del ciclo anterior se conservan.
- Si no renueva: cliente (sin paquetes activos) pasa a "No renovados" con toda su info; se guarda **3 meses** y luego se elimina permanentemente (antes eran 12 meses en la propuesta).
- Reingreso: regla de 2 meses se mantiene (continuar vs. nuevo con historial borrado).
- Sin importador de Excel. Datos falsos solo para pruebas.
- Tipo y Paquete: no cambian reglas (etiquetas). Se mantienen dos catálogos salvo que el usuario pida fusionarlos.
- Pregunta 5 sin respuesta: se usa el default (admin con escritura puede capturar por un CM, con bitácora).

## Constantes (config, no hardcodeadas)
CICLO_DIAS=30, TOLERANCIA_DIAS=3, PRORROGA_MAX_DIAS=15, AVISO_DIAS=3, PURGA_MESES=3, REINGRESO_MESES=2
