"""Funciones comunes: fechas, días hábiles y formatos."""
from __future__ import annotations

import calendar
import re
import unicodedata
from datetime import date, datetime, timedelta
from functools import lru_cache

from config import settings


def a_fecha(valor) -> date | None:
    """Convierte texto ISO, datetime o date a date. Vacío -> None."""
    if valor in (None, ""):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor)[:10])


def a_iso(valor) -> str | None:
    f = a_fecha(valor)
    return f.isoformat() if f else None


def ahora_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def dias_inclusivos(inicio, fin) -> int:
    """Días entre dos fechas contando ambos extremos (1 al 3 = 3 días)."""
    return (a_fecha(fin) - a_fecha(inicio)).days + 1


def sumar_meses(fecha, meses: int) -> date:
    f = a_fecha(fecha)
    total = f.month - 1 + meses
    anio, mes = f.year + total // 12, total % 12 + 1
    return date(anio, mes, min(f.day, calendar.monthrange(anio, mes)[1]))


@lru_cache(maxsize=1)
def _festivos_colombia():
    try:
        import holidays
        return holidays.country_holidays("CO")
    except Exception:  # la librería es opcional
        return None


def es_festivo(fecha) -> bool:
    f = a_fecha(fecha)
    if f.isoformat() in settings.FESTIVOS_EXTRA:
        return True
    h = _festivos_colombia()
    return bool(h and f in h)


def es_dia_habil(fecha) -> bool:
    f = a_fecha(fecha)
    return f.weekday() < 5 and not es_festivo(f)


def sumar_dias_habiles(fecha, n: int) -> date:
    """Fecha que resulta de sumar n días hábiles (lunes a viernes, sin festivos)."""
    f = a_fecha(fecha)
    restantes = n
    while restantes > 0:
        f += timedelta(days=1)
        if es_dia_habil(f):
            restantes -= 1
    return f


def dias_habiles_entre(inicio, fin) -> int:
    """Días hábiles transcurridos después de `inicio` hasta `fin` (inclusive)."""
    f, fin = a_fecha(inicio), a_fecha(fin)
    cuenta = 0
    while f < fin:
        f += timedelta(days=1)
        if es_dia_habil(f):
            cuenta += 1
    return cuenta


def primer_dia_mes(anio: int, mes: int) -> date:
    return date(anio, mes, 1)


def ultimo_dia_mes(anio: int, mes: int) -> date:
    return date(anio, mes, calendar.monthrange(anio, mes)[1])


def nombre_seguro(texto: str) -> str:
    """Convierte un nombre en algo válido para carpetas y archivos."""
    sin_tildes = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", sin_tildes).strip("_") or "sin_nombre"


def normalizar_texto(texto) -> str:
    """Minúsculas, sin tildes y sin espacios repetidos: para comparar nombres de usuario."""
    sin_tildes = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.casefold().split())


def moneda(valor) -> str:
    if valor is None:
        return "—"
    return "$" + f"{valor:,.0f}".replace(",", ".")
