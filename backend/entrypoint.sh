#!/bin/sh
set -e

# Migraciones numeradas (idempotentes): se aplican las que falten antes de arrancar
python -m app.migrations.run_migrations

# Solo para desarrollo/pruebas; NUNCA en producción (usa `python -m app.cli crear-admin`)
if [ "$SEED_ON_START" = "true" ]; then
    python -m app.seed || echo "[seed] omitido (ya hay datos)"
fi

RELOAD_FLAG=""
[ "$RELOAD" = "true" ] && RELOAD_FLAG="--reload"

# UN solo proceso: el scheduler (APScheduler) y el límite de intentos de login viven en memoria.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*" $RELOAD_FLAG
