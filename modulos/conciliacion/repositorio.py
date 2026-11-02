"""Acceso a la base de datos del módulo de conciliación."""
from core import database as db


def insertar_pago(datos: dict) -> int:
    return db.insert("pagos_entidad", datos)


def obtener_pago(pago_id: int) -> dict | None:
    return db.fetch_one("SELECT * FROM pagos_entidad WHERE id = ?", (pago_id,))


def insertar_aplicacion(datos: dict) -> int:
    return db.insert("pagos_aplicaciones", datos)


def aplicado_a_pago(pago_id: int) -> float:
    fila = db.fetch_one("SELECT COALESCE(SUM(valor),0) AS t FROM pagos_aplicaciones WHERE pago_id = ?",
                        (pago_id,))
    return float(fila["t"])


def listar_pagos(entidad: str | None = None) -> list[dict]:
    sql, params = "SELECT * FROM pagos_entidad", ()
    if entidad:
        sql, params = sql + " WHERE entidad = ?", (entidad,)
    return db.fetch_all(sql + " ORDER BY fecha_pago DESC, id DESC", params)


def aplicaciones_del_mes(desde: str, hasta: str) -> list[dict]:
    return db.fetch_all(
        "SELECT a.valor, a.dias_pagados, p.entidad, p.fecha_pago, p.referencia, i.id AS incapacidad_id, i.dias, "
        "i.fecha_inicio, i.fecha_fin, i.tipo, c.nombre AS colaborador "
        "FROM pagos_aplicaciones a JOIN pagos_entidad p ON p.id = a.pago_id "
        "JOIN incapacidades i ON i.id = a.incapacidad_id "
        "JOIN colaboradores c ON c.id = i.colaborador_id "
        "WHERE p.fecha_pago BETWEEN ? AND ? ORDER BY p.entidad, c.nombre, i.fecha_inicio",
        (desde, hasta))


def pagadas_sin_aplicacion() -> list[dict]:
    return db.fetch_all(
        "SELECT i.id, i.entidad, i.fecha_inicio, i.fecha_fin, c.nombre AS colaborador "
        "FROM incapacidades i JOIN colaboradores c ON c.id = i.colaborador_id "
        "WHERE i.estado = 'Pagada' AND NOT EXISTS "
        "(SELECT 1 FROM pagos_aplicaciones a WHERE a.incapacidad_id = i.id)")
