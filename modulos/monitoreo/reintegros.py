"""Reintegros: pagos de incapacidades superiores a 180 días que las EPS hacen a los trabajadores (5.5.3)."""
from core import auditoria, consultas
from core.utils import a_fecha
from modulos.monitoreo import repositorio as repo


def registrar(incapacidad_id: int, fecha, valor: float, entidad_pagadora: str = "",
              nota: str = "", usuario="sistema") -> int:
    if valor <= 0:
        raise ValueError("El valor del reintegro debe ser mayor a cero.")
    inc = consultas.obtener_incapacidad(incapacidad_id)
    if not inc:
        raise ValueError("Incapacidad no encontrada.")
    caso_id = consultas.caso_id_de(incapacidad_id)
    if consultas.acumulado_caso_a_fecha(caso_id, inc["fecha_fin"]) <= 180:
        raise ValueError("Solo aplica a casos que superan los 180 días acumulados.")
    rid = repo.insertar_reintegro({"incapacidad_id": incapacidad_id, "fecha": a_fecha(fecha).isoformat(),
                                   "valor": float(valor), "entidad_pagadora": entidad_pagadora,
                                   "nota": nota, "usuario": usuario})
    auditoria.registrar(usuario, "reintegro", "incapacidad", incapacidad_id, f"${valor:,.0f}")
    return rid


def listar() -> list[dict]:
    return repo.listar_reintegros()
