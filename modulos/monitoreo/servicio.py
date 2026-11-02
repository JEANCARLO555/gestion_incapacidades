"""Orquesta el monitoreo de incapacidades prolongadas (5.5.3)."""
from datetime import date

from config import reglas_monitoreo as rm
from core import auditoria, notificaciones
from core.utils import a_fecha
from modulos.monitoreo import comunicaciones, hitos, rehabilitacion, reintegros
from modulos.monitoreo import repositorio as repo


def reporte_mensual(anio: int, mes: int) -> list[dict]:
    return hitos.reporte_mensual(anio, mes)


def casos_del_mes(anio: int, mes: int) -> list[dict]:
    return hitos.casos_del_mes(anio, mes)


def tablero_rehabilitacion(fecha_corte=None) -> list[dict]:
    """Casos activos con lo que hay que hacer en cada uno, los más urgentes primero."""
    filas = []
    for caso in hitos.casos_activos(fecha_corte):
        concepto = repo.obtener_concepto(caso["caso_id"])
        tarea = rehabilitacion.pendiente_de(concepto, caso["dias"])
        if caso["dias"] > rm.DIA_SUSPENSION_PAGO_NOMINA:
            tarea = {**tarea, "mensaje": (tarea["mensaje"] + " " if tarea["mensaje"] else "") +
                     "Supera 180 días: comunicar la suspensión del pago por nómina.",
                     "urgencia": max(tarea["urgencia"], 2)}
        filas.append({"caso_id": caso["caso_id"], "colaborador": caso["colaborador"],
                      "entidad": caso["entidad"], "dias": caso["dias"],
                      "hito": hitos.hito_superado(caso["dias"]) or "—",
                      "accion": tarea["accion"], "urgencia": tarea["urgencia"],
                      "mensaje": tarea["mensaje"], "resultado": (concepto or {}).get("resultado") or "—"})
    return sorted(filas, key=lambda f: (-f["urgencia"], -f["dias"]))


def _caso(caso_id: int, fecha_corte=None) -> dict:
    for c in hitos.casos_activos(fecha_corte):
        if c["caso_id"] == caso_id:
            return c
    raise ValueError("El caso no está activo en la fecha indicada.")


def registrar_solicitud(caso_id: int, fecha, usuario="sistema") -> None:
    repo.guardar_concepto(caso_id, {"fecha_solicitud": a_fecha(fecha).isoformat(), "usuario": usuario})
    auditoria.registrar(usuario, "solicitud concepto rehabilitación", "caso", caso_id)


def registrar_emision(caso_id: int, fecha, resultado: str, usuario="sistema") -> None:
    if resultado not in rm.RESULTADOS_CONCEPTO:
        raise ValueError("El resultado debe ser Favorable o Desfavorable.")
    repo.guardar_concepto(caso_id, {"fecha_emision": a_fecha(fecha).isoformat(),
                                    "resultado": resultado, "usuario": usuario})
    auditoria.registrar(usuario, "concepto emitido", "caso", caso_id, resultado)


def registrar_envio_afp(caso_id: int, fecha, usuario="sistema") -> None:
    concepto = repo.obtener_concepto(caso_id)
    if not concepto or not concepto.get("fecha_emision"):
        raise ValueError("Primero debe registrarse la emisión del concepto.")
    repo.guardar_concepto(caso_id, {"fecha_envio_afp": a_fecha(fecha).isoformat(), "usuario": usuario})


def comunicar_resultado(caso_id: int, fecha, usuario="sistema") -> None:
    concepto = repo.obtener_concepto(caso_id)
    if not concepto or not concepto.get("resultado"):
        raise ValueError("Aún no hay un concepto emitido para comunicar.")
    caso = _caso(caso_id, fecha)
    comunicaciones.comunicar_resultado(caso, concepto["resultado"], usuario)
    repo.guardar_concepto(caso_id, {"fecha_comunicacion_trabajador": a_fecha(fecha).isoformat()})


def notificar_no_expedido(caso_id: int, fecha_corte=None, usuario="sistema") -> int:
    caso = _caso(caso_id, fecha_corte)
    if caso["dias"] <= rm.DIA_LIMITE_SOLICITUD_CONCEPTO_EPS:
        raise ValueError(f"Aún no supera el día {rm.DIA_LIMITE_SOLICITUD_CONCEPTO_EPS}.")
    concepto = repo.obtener_concepto(caso_id)
    if concepto and concepto.get("fecha_emision"):
        raise ValueError("El concepto ya fue expedido.")
    if notificaciones.existe(caso["ultima_id"], "Monitoreo-No expedido"):
        raise ValueError("Ya se notificó que el concepto no fue expedido.")
    return comunicaciones.notificar_concepto_no_expedido(caso, caso["dias"], usuario)


def comunicar_suspension(caso_id: int, fecha_corte=None, usuario="sistema") -> int:
    caso = _caso(caso_id, fecha_corte)
    if caso["dias"] <= rm.DIA_SUSPENSION_PAGO_NOMINA:
        raise ValueError(f"Aún no supera los {rm.DIA_SUSPENSION_PAGO_NOMINA} días.")
    if notificaciones.existe(caso["ultima_id"], "Monitoreo-Suspensión"):
        raise ValueError("Ya se comunicó la suspensión del pago.")
    return comunicaciones.comunicar_suspension_pago(caso, caso["dias"], usuario)


def registrar_reintegro(*args, **kwargs) -> int:
    return reintegros.registrar(*args, **kwargs)


def listar_reintegros() -> list[dict]:
    return reintegros.listar()
