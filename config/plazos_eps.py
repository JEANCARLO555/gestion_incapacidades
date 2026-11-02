"""Plazos de transcripción por entidad (5.2.1) y otros plazos de cobro (5.4)."""
from datetime import date, timedelta

from config import reglas_documentos as rd
from core.utils import a_fecha, sumar_meses

# Tabla 5.2.1 del procedimiento
PLAZOS_TRANSCRIPCION = {
    "Salud Total": {"meses": 12, "por_tipo": {rd.TIPO_ACCIDENTE_TRANSITO: {"dias": 15}}},
    "Nueva EPS": {"meses": 12},
    "SOS": {"meses": 12},
    "Sanitas": {"meses": 36},       # 3 años
    "SURA EPS": {"dias": 150},
    "Asmet Salud": {"meses": 12},
    "ARL SURA": {"meses": 12},
}

# Licencia de paternidad: 30 días calendario desde el nacimiento, para todas las EPS
PLAZO_PATERNIDAD_DIAS = 30

# 5.2: en estas entidades la transcripción NO es digital (correo electrónico y personal)
ENTIDADES_TRANSCRIPCION_MANUAL = {"SOS", "Sanitas", "Famisanar"}

# 5.4.1: las entidades tienen máximo 3 años para pagar
LIMITE_PAGO_ENTIDAD_ANIOS = 3

# Supuesto: el procedimiento no dice desde cuándo corre el plazo.
# Se cuenta desde la fecha de INICIO de la incapacidad (o el nacimiento en paternidad).
# Si la política es otra, cambiar solo la función de abajo.


def plazo_transcripcion(entidad: str, tipo: str) -> dict | None:
    """Devuelve {'meses': n} o {'dias': n}; None si el procedimiento no lo define."""
    if tipo == rd.TIPO_LICENCIA_PATERNIDAD:
        return {"dias": PLAZO_PATERNIDAD_DIAS}
    datos = PLAZOS_TRANSCRIPCION.get(entidad)
    if not datos:
        return None
    if tipo in datos.get("por_tipo", {}):
        return datos["por_tipo"][tipo]
    return {k: v for k, v in datos.items() if k in ("meses", "dias")}


def fecha_limite_transcripcion(entidad, tipo, fecha_inicio, fecha_nacimiento=None) -> date | None:
    plazo = plazo_transcripcion(entidad, tipo)
    if not plazo:
        return None
    base = a_fecha(fecha_nacimiento) if (tipo == rd.TIPO_LICENCIA_PATERNIDAD and fecha_nacimiento) \
        else a_fecha(fecha_inicio)
    if "meses" in plazo:
        return sumar_meses(base, plazo["meses"])
    return base + timedelta(days=plazo["dias"])


def descripcion_plazo(entidad: str, tipo: str) -> str:
    p = plazo_transcripcion(entidad, tipo)
    if not p:
        return "Sin plazo definido en el procedimiento"
    if "dias" in p:
        return f"{p['dias']} días calendario"
    m = p["meses"]
    return f"{m // 12} años" if m % 12 == 0 and m >= 24 else f"{m} meses"
