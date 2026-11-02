"""Acceso a la base de datos del módulo de cartera."""
from core import database as db


def contar_gestiones(inc_id: int, tipo: str) -> int:
    fila = db.fetch_one("SELECT COUNT(*) AS n FROM gestiones_cobro WHERE incapacidad_id = ? "
                        "AND tipo = ?", (inc_id, tipo))
    return fila["n"]


def actualizar_incapacidad(inc_id: int, campos: dict) -> None:
    db.update("incapacidades", inc_id, campos)
