"""Acceso a la base de datos del módulo de transcripción."""
from core import database as db


def insertar_transcripcion(datos: dict) -> int:
    return db.insert("transcripciones", datos)


def historial(inc_id: int) -> list[dict]:
    return db.fetch_all("SELECT * FROM transcripciones WHERE incapacidad_id = ? ORDER BY id",
                        (inc_id,))


def rechazo_subsanado(inc_id: int) -> bool:
    """True si el último rechazo ya fue subsanado y se puede transcribir de nuevo."""
    fila = db.fetch_one("SELECT subsanado FROM rechazos WHERE incapacidad_id = ? "
                        "ORDER BY id DESC LIMIT 1", (inc_id,))
    return bool(fila and fila["subsanado"])
