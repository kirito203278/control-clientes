# Cómo ejecutar (desarrollo)

Requisitos: Docker + Docker Compose (o un Postgres propio y Python 3.12+).

```bash
python3 scripts/generar_env.py            # una vez: crea .env con claves NUEVAS
docker compose up -d --build              # Postgres + backend (migra solo al arrancar) + Adminer
docker compose exec backend python -m app.seed    # datos de ejemplo (ficticios)
```

- API: http://localhost:8000/api/health · Adminer (visor de BD): http://localhost:8081
- Las contraseñas de los usuarios de prueba quedan en `backend/seed_credentials.txt` (ignorado por git).
- Volver a sembrar desde cero (solo dev): `docker compose exec -e FORCE_SEED=true backend python -m app.seed`
- Solo migraciones: `docker compose exec backend python -m app.migrations.run_migrations`

## Pruebas automatizadas (necesitan Postgres; crean y borran su propia base temporal)
```bash
docker compose up -d db
cd backend && python3 -m venv ../.venv && . ../.venv/bin/activate && pip install -r requirements-dev.txt
python -m pytest -q          # toma credenciales de ../.env; o define TEST_DATABASE_URL
```
