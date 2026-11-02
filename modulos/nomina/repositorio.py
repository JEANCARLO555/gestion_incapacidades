"""Acceso a la base de datos del módulo de nómina."""
from core import database as db


def obtener(inc_id: int, periodo: str) -> dict | None:
    return db.fetch_one("SELECT * FROM nomina_novedades WHERE incapacidad_id = ? AND periodo = ?",
                        (inc_id, periodo))


def guardar(datos: dict) -> None:
    existente = obtener(datos["incapacidad_id"], datos["periodo"])
    if existente:
        db.update("nomina_novedades", existente["id"], datos)
    else:
        db.insert("nomina_novedades", datos)


def listar_periodo(periodo: str) -> list[dict]:
    return db.fetch_all(
        "SELECT n.*, c.nombre AS colaborador, c.documento, i.tipo, i.entidad, i.fecha_inicio, i.fecha_fin "
        "FROM nomina_novedades n JOIN incapacidades i ON i.id = n.incapacidad_id "
        "JOIN colaboradores c ON c.id = i.colaborador_id WHERE n.periodo = ? ORDER BY c.nombre",
        (periodo,))


def marcar_reportada(novedad_id: int, fecha: str) -> None:
    db.update("nomina_novedades", novedad_id, {"reportada": 1, "fecha_reporte": fecha})
