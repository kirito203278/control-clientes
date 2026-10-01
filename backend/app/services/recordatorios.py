"""Recordatorio de pago para el cliente: texto ya redactado + enlace wa.me (sin APIs de mensajería)."""
import datetime as dt
import re
from decimal import Decimal
from urllib.parse import quote

from app.config import get_settings


def normalizar_telefono(telefono: str | None) -> str | None:
    """Dígitos listos para wa.me. México: 10 dígitos -> 52 + 10; '521' + 10 -> '52' + 10."""
    if not telefono:
        return None
    d = re.sub(r"\D", "", telefono)
    if len(d) == 10:
        return "52" + d
    if len(d) == 13 and d.startswith("521"):
        return "52" + d[3:]
    if len(d) == 12 and d.startswith("52"):
        return d
    return d if len(d) >= 11 else None


def armar_texto(cliente_nombre: str, paquete: str, restante: Decimal, fecha_limite: dt.date | None) -> str:
    agencia = get_settings().agencia_nombre
    plazo = f" El plazo acordado venció el {fecha_limite.strftime('%d/%m/%Y')}." if fecha_limite else ""
    return (f"Hola, {cliente_nombre}. Te escribimos de {agencia}. Te recordamos que tu paquete {paquete} "
            f"tiene un saldo pendiente de ${restante:,.2f}.{plazo} ¿Nos confirmas cuándo podrías realizar "
            f"tu pago? Si ya lo hiciste, ¡mil gracias y perdona la molestia!")


def wa_url(telefono: str | None, texto: str) -> str | None:
    tel = normalizar_telefono(telefono)
    return f"https://wa.me/{tel}?text={quote(texto)}" if tel else None
