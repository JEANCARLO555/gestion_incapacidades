"""
Rutas de los archivos digitales.

Se guardan en la base de datos RELATIVAS a la carpeta archivos_digitales/, así el proyecto se puede
mover a otro lugar o computador sin perder los archivos. Las rutas absolutas guardadas por versiones
anteriores se siguen entendiendo.
"""
from pathlib import Path

from config import settings

NOMBRE_CARPETA = "archivos_digitales"


def a_relativa(ruta) -> str:
    try:
        return Path(ruta).resolve().relative_to(settings.ARCHIVOS_DIR.resolve()).as_posix()
    except ValueError:
        return str(ruta)


def a_absoluta(ruta_guardada) -> Path:
    p = Path(str(ruta_guardada))
    if not p.is_absolute():
        return settings.ARCHIVOS_DIR / p
    if p.exists():
        return p
    partes = p.parts
    if NOMBRE_CARPETA in partes:        # el proyecto se movió: se reconstruye desde la carpeta actual
        i = len(partes) - 1 - partes[::-1].index(NOMBRE_CARPETA)
        return settings.ARCHIVOS_DIR.joinpath(*partes[i + 1:])
    return p


def esta_dentro(ruta: Path) -> bool:
    """True si la ruta apunta realmente dentro de archivos_digitales/ (evita salirse con «..»)."""
    try:
        Path(ruta).resolve().relative_to(settings.ARCHIVOS_DIR.resolve())
        return True
    except ValueError:
        return False
