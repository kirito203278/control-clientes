"""Pruebas de integración contra un Postgres REAL (no SQLite: el esquema usa CHECK,
vistas, triggers y JSONB).

Servidor de pruebas: variable TEST_DATABASE_URL (una URL de servidor con permiso para
crear bases, p. ej. postgresql://usuario:clave@localhost:5434/postgres). Si no está, se
arma desde ../.env apuntando a localhost:DB_PORT (`docker compose up -d db`).
Cada corrida crea una base temporal y la borra al final."""
import base64
import os
import secrets
import uuid
from pathlib import Path

import psycopg2
import pytest
from dotenv import dotenv_values

# Secretos efímeros ANTES de importar app.* (Settings los exige)
os.environ.setdefault("JWT_SECRET", secrets.token_urlsafe(32))
os.environ.setdefault("AES_KEY_B64", base64.b64encode(secrets.token_bytes(32)).decode())
os.environ.setdefault("JOBS_SECRET", secrets.token_urlsafe(16))
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://x:x@localhost/x")  # no se usa en pruebas

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.migrations.run_migrations import run_migrations  # noqa: E402


def _server_url() -> str | None:
    if os.getenv("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]
    env = Path(__file__).resolve().parents[2] / ".env"
    if env.exists():
        v = dotenv_values(env)
        if v.get("POSTGRES_USER") and v.get("POSTGRES_PASSWORD"):
            return f"postgresql://{v['POSTGRES_USER']}:{v['POSTGRES_PASSWORD']}@localhost:{v.get('DB_PORT', '5434')}/postgres"
    return None


@pytest.fixture(scope="session")
def test_db_url():
    server = _server_url()
    if not server:
        pytest.skip("Sin servidor Postgres de pruebas (define TEST_DATABASE_URL o levanta `docker compose up -d db`)")
    nombre = f"cc_test_{uuid.uuid4().hex[:8]}"
    admin = psycopg2.connect(server)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(f'CREATE DATABASE "{nombre}"')
    base, _, _ = server.rpartition("/")
    url = f"{base}/{nombre}"
    run_migrations(url.replace("postgresql://", "postgresql+psycopg2://"))
    yield url
    with admin.cursor() as cur:
        cur.execute(f'DROP DATABASE "{nombre}" WITH (FORCE)')
    admin.close()


@pytest.fixture(scope="session")
def engine(test_db_url):
    eng = create_engine(test_db_url.replace("postgresql://", "postgresql+psycopg2://"))
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    """Sesión aislada: todo lo que haga la prueba (incluidos commit del seed) se revierte."""
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
    yield session
    session.close()
    trans.rollback()
    conn.close()


# ----------------------------------------------------------------- API / fábricas
from fastapi.testclient import TestClient  # noqa: E402

from app.security import passwords, rate_limit  # noqa: E402

passwords.BCRYPT_ROUNDS = 4


@pytest.fixture(autouse=True)
def _limpiar_rate_limit():
    rate_limit.reiniciar_todo()


@pytest.fixture
def api(db):
    from app.database import get_db
    from app.main import app
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def crear_usuario(db):
    from app.models import Usuario

    def _crear(username, rol="cm", solo_lectura=False, activo=True, password="Clave-de-prueba-1"):
        u = Usuario(nombre=username.split(".")[0].title(), username=username, rol=rol, solo_lectura=solo_lectura,
                    activo=activo, password_hash=passwords.hash_password(password))
        db.add(u)
        db.flush()
        u._password = password
        return u
    return _crear


@pytest.fixture
def auth(api):
    """auth(usuario) -> headers con un JWT válido."""
    def _auth(u):
        r = api.post("/api/auth/login", json={"username": u.username, "password": u._password})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}
    return _auth
