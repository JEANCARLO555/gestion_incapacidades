"""Acceso a la base de datos del módulo de liquidación."""
from core import consultas


def listar_liquidables() -> list[dict]:
    return consultas.listar_incapacidades(orden="i.fecha_inicio DESC, i.id DESC")
