"""Configuración central, leída de variables de entorno / .env.

Los secretos (JWT_SECRET, AES_KEY_B64, JOBS_SECRET, DATABASE_URL) NO tienen
valor por defecto: sin .env la app no arranca, en vez de arrancar insegura.
"""
from functools import lru_cache

import base64
import binascii

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str
    jwt_secret: str
    aes_key_b64: str          # 32 bytes en base64 (AES-256)
    jobs_secret: str          # header X-Jobs-Secret para los endpoints de cron externo

    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    tz: str = "America/Mexico_City"
    agencia_nombre: str = "INNquietus"
    scheduler_enabled: bool = True
    enable_docs: bool = False   # /docs (OpenAPI) solo en desarrollo

    # Reglas de negocio parametrizables (ver ESTADO.md)
    ciclo_dias: int = 30                  # duración de un ciclo
    prorroga_max_dias: int = 5            # naturales, desde que se activa la prórroga (la fecha es automática)
    dias_para_decidir: int = 2            # días con la ventana de bloqueo activa antes de pasar a No renovados
    aviso_dias_antes_renovacion: int = 4  # aviso "¿renueva?" (3 días antes de la fecha límite = R-1)
    aviso_prorroga_dias: int = 3          # aviso antes de vencer una prórroga
    purga_meses: int = 12                 # permanencia máxima en "No renovados" (1 año)
    reingreso_meses: int = 2              # <2 meses: puede continuar; >=2: paquete nuevo y se borra historial

    @field_validator("database_url")
    @classmethod
    def _normalizar_url_bd(cls, v: str) -> str:
        """Neon/Render entregan postgres:// o postgresql://; SQLAlchemy necesita el driver explícito."""
        for prefijo in ("postgres://", "postgresql://"):
            if v.startswith(prefijo):
                return "postgresql+psycopg2://" + v[len(prefijo):]
        return v

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_fuerte(cls, v: str) -> str:
        if len(v) < 32 or v.startswith("__"):
            raise ValueError("JWT_SECRET debe tener al menos 32 caracteres (genera uno con scripts/generar_env.py)")
        return v

    @field_validator("jobs_secret")
    @classmethod
    def _jobs_fuerte(cls, v: str) -> str:
        if len(v) < 16 or v.startswith("__"):
            raise ValueError("JOBS_SECRET debe tener al menos 16 caracteres (genera uno con scripts/generar_env.py)")
        return v

    @field_validator("aes_key_b64")
    @classmethod
    def _aes_valida(cls, v: str) -> str:
        try:
            ok = len(base64.b64decode(v, validate=True)) == 32
        except (binascii.Error, ValueError):
            ok = False
        if not ok:
            raise ValueError("AES_KEY_B64 debe ser una clave de 32 bytes en base64 (genera una con scripts/generar_env.py)")
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
