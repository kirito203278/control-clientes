# Cómo ejecutar

## Todo en uno con Docker (recomendado para probar)
Requisitos: Docker + Docker Compose.

```bash
python3 scripts/generar_env.py            # una vez: crea .env con claves NUEVAS (nunca reutilices las de otro proyecto)
docker compose up -d --build              # Postgres + app (API e interfaz) + Adminer
docker compose exec backend python -m app.seed   # datos de ejemplo FICTICIOS (solo desarrollo)
```

- Aplicación: http://localhost:8000 · Adminer (visor de BD): http://localhost:8081
- Las contraseñas de los usuarios de ejemplo (`admin.demo`, `lectura.demo`, `ana.ruiz`, `beto.luna`, `carla.soto`) quedan en
  `backend/seed_credentials.txt` dentro del contenedor: `docker compose exec backend cat seed_credentials.txt`.
- Volver a sembrar desde cero (solo dev): `docker compose exec -e FORCE_SEED=true backend python -m app.seed`
- Crear un admin sin datos de ejemplo: `docker compose exec backend python -m app.cli crear-admin "Nombre Apellido"`
- Disparar un job a mano: `docker compose exec backend python -c "from app.jobs import tareas; print(tareas.ejecutar('renovaciones'))"`
  (nombres: `renovaciones`, `prorrogas`, `purga_no_renovados`).

## Desarrollo con recarga en vivo
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build   # backend con --reload en :8000
cd frontend && npm install && npm run dev                                       # interfaz en http://localhost:5173 (proxy a :8000)
```

## Sin Docker
Necesitas un PostgreSQL propio y Python 3.14. Ajusta `DATABASE_URL` en `.env` y:
```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r backend/requirements-dev.txt
cd backend && python -m app.migrations.run_migrations && python -m app.seed && uvicorn app.main:app --port 8000
cd ../frontend && npm install && npm run build      # compila a backend/app/static; el backend lo sirve en el mismo puerto
```

## Pruebas automatizadas
Necesitan un Postgres con permiso para crear bases (cada corrida crea y borra la suya):
```bash
docker compose up -d db
cd backend && . ../.venv/bin/activate && python -m pytest -q       # toma credenciales de ../.env; o define TEST_DATABASE_URL
```
Reglas críticas cubiertas: bloqueo por contrato vencido, prórroga de 5 días, mensaje de una sola vez, aislamiento por `cm_id`, reglas de reingreso y purga a 1 año, periodos y cortes de
quincena, jobs idempotentes, reportes (incluido recálculo de fórmulas del Excel con LibreOffice si está instalado).

## Producción
Ver **docs/DESPLIEGUE.md** (Render + Neon, cron-job.org, UptimeRobot, respaldos).
