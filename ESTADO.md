# ESTADO — Control de clientes INNquietus

Referencia de solo lectura: `~/Documentos/referencia/sistema-campanas-master` (no modificar, no copiar entero).

## Fases
- [x] Fase 0 — Diseño: `docs/FASE0_esquema.sql`, `docs/FASE0_endpoints.md`. **Esperando respuestas a 5 preguntas.**
- [ ] Fase 1 — BD, migraciones, seed, Docker, `.env`
- [ ] Fase 2 — Auth, roles, equipo, reasignación/baja
- [ ] Fase 3 — Panel CM
- [ ] Fase 4 — Renovación, No renovados, notificaciones, jobs
- [ ] Fase 5 — Ingresos, importador CSV, recordatorios WhatsApp
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
