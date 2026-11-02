"""Acceso a la base de datos del módulo de archivo."""
from core import database as db


def obtener(inc_id: int) -> dict | None:
    return db.fetch_one("SELECT * FROM archivo_fisico WHERE incapacidad_id = ?", (inc_id,))


def guardar(inc_id: int, campos: dict) -> None:
    existente = obtener(inc_id)
    if existente:
        db.update("archivo_fisico", existente["id"], campos)
    else:
        db.insert("archivo_fisico", {"incapacidad_id": inc_id, **campos})


def listado_fisico() -> list[dict]:
    return db.fetch_all(
        "SELECT a.*, i.entidad, i.fecha_inicio, i.fecha_fin, i.estado, c.nombre AS colaborador "
        "FROM archivo_fisico a JOIN incapacidades i ON i.id = a.incapacidad_id "
        "JOIN colaboradores c ON c.id = i.colaborador_id ORDER BY i.entidad, i.fecha_inicio ASC")


def archivos_clinicos_vigentes(inc_id: int) -> list[dict]:
    return db.fetch_all("SELECT * FROM archivos_digitales WHERE incapacidad_id = ? "
                        "AND es_clinico = 1 AND eliminado_en IS NULL", (inc_id,))


def marcar_eliminado(archivo_id: int, fecha: str) -> None:
    db.update("archivos_digitales", archivo_id, {"eliminado_en": fecha})


def carpetas_con_archivos() -> list[dict]:
    return db.fetch_all(
        "SELECT i.id AS incapacidad_id, c.nombre AS colaborador, i.entidad, i.tipo, i.fecha_inicio, "
        "i.fecha_fin, i.estado, COUNT(a.id) AS archivos, MAX(a.subido_en) AS ultima_carga, "
        "MIN(a.ruta) AS ruta_ejemplo FROM archivos_digitales a "
        "JOIN incapacidades i ON i.id = a.incapacidad_id JOIN colaboradores c ON c.id = i.colaborador_id "
        "WHERE a.eliminado_en IS NULL GROUP BY i.id ORDER BY ultima_carga DESC, i.id DESC")


def archivos_vigentes(inc_id: int) -> list[dict]:
    return db.fetch_all("SELECT * FROM archivos_digitales WHERE incapacidad_id = ? "
                        "AND eliminado_en IS NULL ORDER BY subido_en DESC, id DESC", (inc_id,))


def obtener_archivo(archivo_id: int) -> dict | None:
    return db.fetch_one("SELECT * FROM archivos_digitales WHERE id = ? AND eliminado_en IS NULL",
                        (archivo_id,))
