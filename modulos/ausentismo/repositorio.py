"""Acceso a la base de datos del módulo de ausentismo."""
from core import database as db


def incapacidades_del_periodo(desde: str, hasta: str) -> list[dict]:
    return db.fetch_all(
        "SELECT i.id, c.nombre AS colaborador, c.area, i.tipo, i.entidad, i.fecha_inicio, i.fecha_fin "
        "FROM incapacidades i JOIN colaboradores c ON c.id = i.colaborador_id "
        "WHERE i.fecha_inicio <= ? AND i.fecha_fin >= ? ORDER BY i.fecha_inicio", (hasta, desde))


def colaboradores_activos() -> int:
    return db.fetch_one("SELECT COUNT(*) AS n FROM colaboradores WHERE activo = 1")["n"]


def reporte_enviado(periodo: str) -> dict | None:
    return db.fetch_one("SELECT * FROM reportes_ausentismo WHERE periodo = ?", (periodo,))


def guardar_envio(datos: dict) -> int:
    return db.insert("reportes_ausentismo", datos)
