"""Acceso a la base de datos del módulo de verificación documental."""
from core import database as db
from core.utils import ahora_iso


def actualizar_documentos(inc_id: int, recibidos: set[str]) -> None:
    for d in db.fetch_all("SELECT id, documento FROM documentos_incapacidad "
                          "WHERE incapacidad_id = ?", (inc_id,)):
        db.update("documentos_incapacidad", d["id"], {"recibido": int(d["documento"] in recibidos)})


def actualizar_llegada_fisica(inc_id: int, llegada: bool) -> None:
    db.update("incapacidades", inc_id, {"llegada_fisica": int(llegada)})


def llamados_de(inc_id: int) -> list[dict]:
    return db.fetch_all("SELECT * FROM llamados_documentacion WHERE incapacidad_id = ? "
                        "ORDER BY numero", (inc_id,))


def insertar_llamado(datos: dict) -> int:
    return db.insert("llamados_documentacion", datos)


def insertar_archivo(datos: dict) -> int:
    return db.insert("archivos_digitales", datos)


def archivos_de(inc_id: int) -> list[dict]:
    return db.fetch_all("SELECT * FROM archivos_digitales WHERE incapacidad_id = ? "
                        "AND eliminado_en IS NULL ORDER BY id", (inc_id,))
