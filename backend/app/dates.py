"""Fechas de negocio en America/Mexico_City."""
import datetime as dt
from zoneinfo import ZoneInfo

from app.config import get_settings


def ahora() -> dt.datetime:
    return dt.datetime.now(ZoneInfo(get_settings().tz))


def hoy() -> dt.date:
    return ahora().date()
