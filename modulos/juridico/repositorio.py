"""Acceso a la base de datos del módulo jurídico."""
from core import database as db


def rechazo_improcedente(inc_id: int) -> bool:
    fila = db.fetch_one("SELECT improcedente FROM rechazos WHERE incapacidad_id = ? "
                        "ORDER BY id DESC LIMIT 1", (inc_id,))
    return bool(fila and fila["improcedente"])


def marcar_respondida(gestion_id: int) -> None:
    db.update("gestiones_cobro", gestion_id, {"respondida": 1})


def obtener_gestion(gestion_id: int) -> dict | None:
    return db.fetch_one("SELECT * FROM gestiones_cobro WHERE id = ?", (gestion_id,))
