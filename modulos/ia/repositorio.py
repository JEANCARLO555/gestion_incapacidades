"""Acceso a la base de datos del módulo de IA/analítica (solo lectura)."""
from core import database as db


def incapacidades_con_colaborador() -> list[dict]:
    return db.fetch_all(
        "SELECT i.id, i.colaborador_id, c.area, i.tipo, i.entidad, i.fecha_inicio, i.fecha_fin, i.dias, "
        "i.fecha_recepcion, i.estado, i.prorroga_de, c.nombre AS colaborador "
        "FROM incapacidades i JOIN colaboradores c ON c.id = i.colaborador_id")


def historial() -> list[dict]:
    return db.fetch_all("SELECT incapacidad_id, estado_nuevo, fecha FROM historial_estados")


def rechazos() -> list[dict]:
    return db.fetch_all("SELECT incapacidad_id FROM rechazos")
