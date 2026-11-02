"""Acceso a la base de datos del módulo de seguimiento de cobro."""
from core import database as db


def conteo_por_estado() -> list[dict]:
    return db.fetch_all("SELECT estado, COUNT(*) AS cantidad FROM incapacidades "
                        "GROUP BY estado ORDER BY cantidad DESC")


def insertar_rechazo(datos: dict) -> int:
    return db.insert("rechazos", datos)


def ultimo_rechazo(inc_id: int) -> dict | None:
    return db.fetch_one("SELECT * FROM rechazos WHERE incapacidad_id = ? ORDER BY id DESC LIMIT 1",
                        (inc_id,))


def marcar_subsanado(rechazo_id: int) -> None:
    db.update("rechazos", rechazo_id, {"subsanado": 1})


def actualizar_promesa_pago(inc_id: int, fecha_iso: str | None) -> None:
    db.update("incapacidades", inc_id, {"fecha_promesa_pago": fecha_iso})


def ultima_gestion(inc_id: int, tipo: str) -> dict | None:
    return db.fetch_one("SELECT * FROM gestiones_cobro WHERE incapacidad_id = ? AND tipo = ? "
                        "ORDER BY fecha DESC, id DESC LIMIT 1", (inc_id, tipo))
