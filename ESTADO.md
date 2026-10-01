# ESTADO — Control de clientes INNquietus

Referencia de solo lectura: `~/Documentos/referencia/sistema-campanas-master` (no modificar, no copiar entero).

## Fases
- [x] Fase 0 — Diseño: `docs/FASE0_esquema.sql`, `docs/FASE0_endpoints.md`. **Cerrada**: todas las preguntas respondidas.
- [x] Fase 1 — BD, migraciones, seed, Docker, `.env` (ver COMO_EJECUTAR.md). Pendiente del usuario: probar con Docker real (aquí no había Docker; se probó con Postgres 18 embebido).
- [x] Fase 2 — Auth, roles, equipo, baja de CM con migración (la reasignación de clientes sueltos va junto al router de clientes, Fase 3)
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
- Línea de tiempo (R = día de renovación): aviso "¿renueva?" en R-4 (3 días antes de la fecha límite R-1) · fecha límite R-1 · vencido en R sin decisión · tolerancia de pago R..R+3 (contada desde R, default no contestado) · después, prórroga obligatoria si hay deuda. Ejemplo: R=10 nov → aviso 6 nov, límite 9 nov, tolerancia hasta 13 nov.
- Si renueva: ventana para conservar los mismos paquetes u otros; deudas/paquetes del ciclo anterior se conservan.
- Si no renueva: cliente (sin paquetes activos) pasa a "No renovados" con toda su info; se guarda **3 meses** y luego se elimina permanentemente (antes eran 12 meses en la propuesta).
- Reingreso: regla de 2 meses se mantiene (continuar vs. nuevo con historial borrado).
- Sin importador de Excel. Datos falsos solo para pruebas.
- Tipo y Paquete: no cambian reglas (etiquetas). Confirmado (opción A): dos catálogos, el Tipo es solo etiqueta.
- Pregunta 5 sin respuesta: se usa el default (admin con escritura puede capturar por un CM, con bitácora).

## Constantes (config, no hardcodeadas)
CICLO_DIAS=30, TOLERANCIA_DIAS=3, PRORROGA_MAX_DIAS=15, AVISO_DIAS_ANTES_RENOVACION=4, PURGA_MESES=3, REINGRESO_MESES=2

## Fase 1 — lo construido
- `backend/app/migrations/sql/`: `001_init.sql` (esquema + trigger `actualizado_en`), `002_catalogos_base.sql`. Runner idempotente con `schema_migrations`.
- Modelos ORM (`app/models.py`), config sin secretos por defecto (`app/config.py`), AES-GCM, bcrypt y contraseñas de 18 caracteres.
- `app/seed.py`: 5 usuarios (admin.demo, lectura.demo, ana.ruiz, beto.luna, carla.soto) y 15 clientes ficticios con fechas relativas a hoy que cubren: por vencer, vencido, amarillo/verde, prórroga por vencer, prórroga vencida con deuda, historial de renovación (Estándar→Élite), multi-paquete, por reasignar y No renovados de 20/70/95 días.
- `scripts/generar_env.py` crea `.env` (600) con claves nuevas. `docker-compose.yml`: db (127.0.0.1:5434), backend (:8000), adminer (:8081).
- 21 pruebas (CHECK de prórroga 15 días, estados, pagos, derivación de `pagado`, dedupe de notificaciones, CASCADE de No renovados, cifrado, seed).
- Dockerfile de una etapa; se vuelve de dos etapas en la Fase 7.
- Python local de desarrollo: 3.14; imagen Docker: 3.12 (requirements con `>=`).
