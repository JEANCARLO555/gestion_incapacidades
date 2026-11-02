"""Conexión a SQLite y funciones de lectura/escritura que usan todos los módulos."""
import sqlite3
from contextlib import contextmanager

from config import settings
from core import models


@contextmanager
def get_connection():
    settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(settings.DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _migrar(con) -> None:
    """Agrega columnas nuevas a bases de datos creadas con versiones anteriores."""
    columnas = {r["name"] for r in con.execute("PRAGMA table_info(pagos_aplicaciones)")}
    if "dias_pagados" not in columnas:
        con.execute("ALTER TABLE pagos_aplicaciones ADD COLUMN dias_pagados INTEGER")


def init_db() -> None:
    with get_connection() as con:
        con.executescript(models.SCHEMA)
        _migrar(con)


def fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    with get_connection() as con:
        return [dict(r) for r in con.execute(sql, params).fetchall()]


def fetch_one(sql: str, params: tuple = ()) -> dict | None:
    with get_connection() as con:
        fila = con.execute(sql, params).fetchone()
        return dict(fila) if fila else None


def execute(sql: str, params: tuple = ()) -> int:
    """Ejecuta una escritura y devuelve el id insertado (o 0)."""
    with get_connection() as con:
        return con.execute(sql, params).lastrowid or 0


def insert(tabla: str, datos: dict) -> int:
    columnas = ", ".join(datos)
    marcas = ", ".join("?" for _ in datos)
    return execute(f"INSERT INTO {tabla} ({columnas}) VALUES ({marcas})", tuple(datos.values()))


def update(tabla: str, id_: int, datos: dict) -> None:
    asignaciones = ", ".join(f"{c} = ?" for c in datos)
    execute(f"UPDATE {tabla} SET {asignaciones} WHERE id = ?", (*datos.values(), id_))
