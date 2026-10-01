"""Configuración central, leída de variables de entorno / .env.

Los secretos (JWT_SECRET, AES_KEY_B64, JOBS_SECRET, DATABASE_URL) NO tienen
valor por defecto: sin .env la app no arranca, en vez de arrancar insegura.
"""
from functools import lru_cache

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

    # Reglas de negocio parametrizables (ver ESTADO.md)
    ciclo_dias: int = 30                  # duración de un ciclo
    tolerancia_dias: int = 3              # días de gracia de pago, contados desde la fecha de renovación
    prorroga_max_dias: int = 15           # naturales, desde que se registra la prórroga
    aviso_dias_antes_renovacion: int = 4  # aviso "¿renueva?" (3 días antes de la fecha límite = R-1)
    aviso_prorroga_dias: int = 3          # aviso antes de vencer una prórroga
    purga_meses: int = 3                  # permanencia máxima en "No renovados"
    reingreso_meses: int = 2              # <2 meses: puede continuar; >=2: paquete nuevo y se borra historial

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
