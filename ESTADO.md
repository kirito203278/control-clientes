# ESTADO — Control de clientes INNquietus

Referencia de solo lectura: `~/Documentos/referencia/sistema-campanas-master` (no modificar, no copiar entero).

## Fases
- [x] Fase 0 — Diseño: `docs/FASE0_esquema.sql`, `docs/FASE0_endpoints.md`. **Cerrada**: todas las preguntas respondidas.
- [x] Fase 1 — BD, migraciones, seed, Docker, `.env` (ver COMO_EJECUTAR.md). Pendiente del usuario: probar con Docker real (aquí no había Docker; se probó con Postgres 18 embebido).
- [x] Fase 2 — Auth, roles, equipo, baja de CM con migración (la reasignación de clientes sueltos va junto al router de clientes, Fase 3)
- [x] Fase 3 — Panel CM (backend + frontend)
- [x] Fase 4 — Renovación, No renovados, notificaciones, jobs (backend + frontend)
- [x] Fase 5 — Ingresos (pantalla CM y admin), recordatorios WhatsApp (SIN importador: la cartera arranca de cero)
- [x] Fase 6 — Reportes PDF/Excel + pruebas (incl. recálculo de fórmulas con LibreOffice) y vista previa en pantalla
- [x] Fase 7 — Producción: Dockerfile de dos etapas, secretos validados, CLI del primer admin, render.yaml, docs/DESPLIEGUE.md

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

## Decisiones de Ingresos y Reportes (Fases 5-6)
- Un solo generador (`services/reporte_datos.py`) alimenta la pantalla Ingresos, el JSON, el PDF y el Excel.
- Proyección = costo de ciclos con fecha de renovación en el periodo, excluyendo archivados y eliminados. Cobrado = pagos de esos ciclos con fecha <= corte (hoy). Un periodo cerrado se reporta completo (los pagos tardíos de un periodo viejo SÍ cuentan: el reporte es "cuánto de lo proyectado se ha cobrado a hoy").
- Periodo en curso (hoy <= último día) = "Periodo parcial, corte al hoy"; la proyección es la del periodo completo. 2da quincena termina el último día real (28/29/30/31).
- Secciones 4 (Prórrogas) y 5 (Pendientes) NO se limitan al periodo: son listas de trabajo con todo lo vigente a la fecha de corte.
- Tasa de renovación = renovados / (ciclos que llegaron a su fecha en el periodo, incluidos archivados/eliminados).
- Reportes: CM obtiene el mismo generador filtrado por su cartera (el `cm_id` de la petición se ignora para un CM). Admin de solo lectura puede descargar.
- Excel: hoja por sección; totales y derivados (restante, %, días, SUMIFS por CM) son fórmulas reales, verificadas recalculando con LibreOffice.

## Regla agregada al final
- Renovar con OTRO paquete reinicia el contador «renovaciones con este paquete» (derivado de la cadena de ciclos, `ciclos.veces_renovado`) y aplica los datos nuevos (paquete, tipo, costo); renovar con el mismo lo incrementa. El historial de ciclos se conserva.

## Pendiente del usuario
- Probar con Docker real (aquí no había Docker; todo se probó con Postgres 18 embebido y uvicorn).
- Desplegar siguiendo docs/DESPLIEGUE.md. docs/FASE0_endpoints.md es el diseño inicial; la API final difiere (prefijos /api/clientes, /api/paquetes...).

## REGLAS ACTUALIZADAS (reemplazan a las anteriores donde choquen)
- **Sin tolerancia de pago.** El contrato termina el día de renovación R a las 23:59 (México). Desde R+1 el paquete queda **bloqueado**
  (se calcula por la fecha, no depende del job): ventana que no se puede cerrar con las salidas válidas:
  *Renovó* (solo si ya pagó completo) · *No renovó* · *Solicitó prórroga* (solo si debe y solo una vez). Mientras haya un paquete
  bloqueado, toda escritura sobre ese cliente se rechaza (409 `bloqueado`) salvo esas tres salidas (aplica también a un admin).
- **Prórroga fija de 5 días naturales** desde que se activa (botón; el CM no elige fecha). Admite pagos parciales o el resto. Si vence
  sin pago completo: el ciclo se archiva solo, el cliente pasa a No renovados (si era su último paquete) y se deja listo el mensaje
  para el cliente + aviso al CM. Si se paga completo en la prórroga, vuelve la ventana (Renovó / No renovó). BD: constraint `prorroga_max_5_dias` (NOT VALID: no rechaza filas viejas).
- **Mensaje al cliente: se envía una sola vez.** Al marcarlo como enviado no se puede generar ni marcar otro del mismo paquete.
- **Sin decisión:** 2 días con la ventana activa (`dias_para_decidir`); después, a las 00:05, pasa solo a No renovados. Con prórroga, el plazo
  corre desde el fin de la prórroga si ya pagó.
- **«No renovará» marcado antes del fin del contrato:** no archiva de inmediato; el job lo archiva al terminar el contrato (se puede deshacer antes).
  Ya vencido, «No renovó» archiva en el momento.
- **No renovados se conservan 1 año** (`purga_meses=12`), ya no 3 meses. Regla de reingreso de 2 meses sin cambio.
- **Fechas automáticas:** al crear un paquete se captura la fecha de **inicio** (renovación = inicio + 30). Al renovar o reingresar el ciclo nuevo empieza
  **HOY** (el día que se confirma) y renueva en 30 días; no se captura fecha. Cambiar el inicio recalcula la renovación y mueve al cliente de quincena
  (1ra = días 1-15, 2da = 16 al último día del mes).
- **Renovó exige el paquete pagado por completo** (si no, prórroga o no renovó). Consecuencia: la columna «Renovados sin pago» del tablero queda para datos históricos.
- Se retiró la pregunta «¿El cliente pagó?» de las notificaciones: ahora el vencimiento de prórroga actúa solo y deja el mensaje listo.
- Jobs: `renovaciones` y `prorrogas` a las 00:05 y 12:00; `purga_no_renovados` a las 12:10.
- Constantes: CICLO_DIAS=30, PRORROGA_MAX_DIAS=5, DIAS_PARA_DECIDIR=2, AVISO_DIAS_ANTES_RENOVACION=4, AVISO_PRORROGA_DIAS=3, PURGA_MESES=12, REINGRESO_MESES=2.

## Contraseñas (cambio posterior)
- Las contraseñas de usuarios ya NO las genera el sistema: el **admin las escribe** al crear un usuario y al cambiarlas (mínimo 8 y máximo 72 caracteres, sin espacios en los bordes; bcrypt).
  La API nunca devuelve una contraseña y la bitácora no las guarda. Un CM no puede cambiar contraseñas.
- Todos los campos de contraseña de la interfaz (login, alta/cambio de usuario, contraseña de Facebook del cliente) tienen botón «Ver/Ocultar» para revisar lo escrito.
  El alta de usuario ofrece «Sugerir una» (aleatoria, generada en el navegador).
- El seed deja contraseñas de EJEMPLO fijas (ver COMO_EJECUTAR.md). El CLI `python -m app.cli crear-admin` sigue generando una contraseña temporal para el primer admin de producción.
