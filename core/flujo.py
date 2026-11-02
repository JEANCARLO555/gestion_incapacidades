"""Cambios de estado y bitácora de gestiones, compartidos por varios módulos."""
from datetime import date, datetime

from config import estados
from core import auditoria, consultas, database as db
from core.utils import a_fecha, ahora_iso


class FlujoError(ValueError):
    """Se intentó una acción que el procedimiento no permite."""


def registrar_estado_inicial(inc_id: int, estado: str, usuario: str) -> None:
    db.insert("historial_estados", {"incapacidad_id": inc_id, "estado_anterior": None,
                                    "estado_nuevo": estado, "fecha": ahora_iso(),
                                    "usuario": usuario, "nota": "Registro inicial"})


def cambiar_estado(inc_id: int, nuevo: str, usuario: str, nota: str = "", fecha=None) -> None:
    inc = consultas.obtener_incapacidad(inc_id)
    if not inc:
        raise FlujoError("Incapacidad no encontrada.")
    actual = inc["estado"]
    if not estados.puede_pasar(actual, nuevo):
        raise FlujoError(f"No se puede pasar de «{actual}» a «{nuevo}».")
    f = a_fecha(fecha) if fecha else None
    marca = datetime.combine(f, datetime.now().time()).isoformat(timespec="seconds") if f else ahora_iso()
    db.update("incapacidades", inc_id, {"estado": nuevo})
    db.insert("historial_estados", {"incapacidad_id": inc_id, "estado_anterior": actual,
                                    "estado_nuevo": nuevo, "fecha": marca,
                                    "usuario": usuario, "nota": nota})
    auditoria.registrar(usuario, "cambio de estado", "incapacidad", inc_id, f"{actual} -> {nuevo}")


def fecha_en_estado(inc_id: int, estado: str, primera: bool = True) -> date | None:
    orden = "ASC" if primera else "DESC"
    fila = db.fetch_one(f"SELECT fecha FROM historial_estados WHERE incapacidad_id = ? "
                        f"AND estado_nuevo = ? ORDER BY fecha {orden}, id {orden} LIMIT 1",
                        (inc_id, estado))
    return a_fecha(fila["fecha"]) if fila else None


def registrar_gestion(inc_id: int, etapa: str, tipo: str, detalle: str, usuario: str,
                      fecha=None, radicado: str | None = None) -> int:
    """Anota una gestión de cobro (deja la evidencia documental que pide el procedimiento)."""
    gid = db.insert("gestiones_cobro", {
        "incapacidad_id": inc_id, "etapa": etapa, "tipo": tipo,
        "fecha": (a_fecha(fecha) or date.today()).isoformat(),
        "detalle": detalle, "radicado": radicado, "usuario": usuario})
    auditoria.registrar(usuario, "gestión de cobro", "incapacidad", inc_id, f"{etapa}: {tipo}")
    return gid
