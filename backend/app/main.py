from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import admin, auth, catalogos, usuarios

settings = get_settings()
app = FastAPI(title="INNquietus · Control de clientes")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth.router, usuarios.router, catalogos.router, admin.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"ok": True}
