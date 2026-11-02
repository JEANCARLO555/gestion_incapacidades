"""Acceso a la base de datos del módulo de monitoreo."""
from core import database as db


def obtener_concepto(caso_id: int) -> dict | None:
    return db.fetch_one("SELECT * FROM conceptos_rehabilitacion WHERE caso_id = ?", (caso_id,))


def guardar_concepto(caso_id: int, campos: dict) -> None:
    existente = obtener_concepto(caso_id)
    if existente:
        db.update("conceptos_rehabilitacion", existente["id"], campos)
    else:
        db.insert("conceptos_rehabilitacion", {"caso_id": caso_id, **campos})


def insertar_reintegro(datos: dict) -> int:
    return db.insert("reintegros", datos)


def listar_reintegros() -> list[dict]:
    return db.fetch_all(
        "SELECT r.*, c.nombre AS colaborador FROM reintegros r "
        "JOIN incapacidades i ON i.id = r.incapacidad_id "
        "JOIN colaboradores c ON c.id = i.colaborador_id ORDER BY r.fecha DESC, r.id DESC")


def incapacidades_cabeza_de_caso() -> list[dict]:
    return db.fetch_all("SELECT id FROM incapacidades WHERE prorroga_de IS NULL ORDER BY id")
