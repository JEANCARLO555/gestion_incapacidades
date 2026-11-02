"""Acceso a la base de datos del módulo de recepción."""
from core import database as db


def buscar_colaborador_por_documento(documento: str) -> dict | None:
    return db.fetch_one("SELECT * FROM colaboradores WHERE documento = ?", (documento,))


def insertar_colaborador(datos: dict) -> int:
    return db.insert("colaboradores", datos)


def insertar_incapacidad(datos: dict) -> int:
    return db.insert("incapacidades", datos)


def insertar_documentos(inc_id: int, documentos: dict[str, bool]) -> None:
    for nombre, recibido in documentos.items():
        db.insert("documentos_incapacidad", {"incapacidad_id": inc_id, "documento": nombre,
                                             "recibido": int(recibido)})


def tiene_prorroga(inc_id: int) -> bool:
    return db.fetch_one("SELECT id FROM incapacidades WHERE prorroga_de = ?", (inc_id,)) is not None


def actualizar_reemplazo(inc_id: int, reemplazo: str) -> None:
    db.update("incapacidades", inc_id, {"reemplazo": reemplazo})


def actualizar_colaborador(colaborador_id: int, datos: dict) -> None:
    db.update("colaboradores", colaborador_id, datos)
