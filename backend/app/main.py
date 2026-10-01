from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.jobs.scheduler import start_scheduler, stop_scheduler
from app.routers import (admin, auth, catalogos, clientes, ingresos, jobs, notificaciones, paquetes, renovacion,
                         reportes, usuarios)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.scheduler_enabled:
        start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="INNquietus · Control de clientes", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth.router, usuarios.router, catalogos.router, admin.router, clientes.router, paquetes.router,
          renovacion.router, notificaciones.router, jobs.router, ingresos.router, reportes.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"ok": True}
