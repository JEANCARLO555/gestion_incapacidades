"""
Transcripción ante la EPS o ARL (5.2, 5.2.1 y pasos 5 y 7).

Se muestra qué incapacidades faltan por transcribir, ordenadas por urgencia
(las de plazo más cercano primero), y se registra la transcripción con la
evidencia documental que pide el procedimiento.
"""
from datetime import date

from config import estados, plazos_eps, settings
from core import consultas, flujo
from core.utils import a_fecha
from modulos.transcripcion import repositorio as repo


def plazo_de(inc: dict, hoy: date | None = None) -> dict:
    hoy = hoy or date.today()
    limite = plazos_eps.fecha_limite_transcripcion(
        inc["entidad"], inc["tipo"], inc["fecha_inicio"], inc.get("fecha_nacimiento"))
    return {"plazo": plazos_eps.descripcion_plazo(inc["entidad"], inc["tipo"]),
            "fecha_limite": limite,
            "dias_restantes": (limite - hoy).days if limite else None,
            "vencido": bool(limite and hoy > limite),
            "manual": inc["entidad"] in plazos_eps.ENTIDADES_TRANSCRIPCION_MANUAL}


def por_transcribir(hoy: date | None = None) -> list[dict]:
    """Verificadas, y rechazadas ya subsanadas; las más urgentes primero."""
    candidatas = consultas.listar_incapacidades(estados=[estados.VERIFICADA, estados.RECHAZADA])
    filas = []
    for inc in candidatas:
        if inc["estado"] == estados.RECHAZADA and not repo.rechazo_subsanado(inc["id"]):
            continue
        filas.append({**inc, **plazo_de(inc, hoy)})
    return sorted(filas, key=lambda f: (f["fecha_limite"] is None, f["fecha_limite"] or date.max))


def registrar_transcripcion(inc_id: int, fecha_transcripcion, medio: str, radicado: str,
                            usuario="sistema", evidencia="", nota="") -> dict:
    inc = consultas.obtener_incapacidad(inc_id)
    if not inc:
        raise flujo.FlujoError("Incapacidad no encontrada.")
    if medio not in settings.MEDIOS_TRANSCRIPCION:
        raise ValueError("Medio de transcripción no válido.")
    info = plazo_de(inc)
    if info["manual"] and medio == settings.MEDIO_PORTAL:
        raise ValueError(f"{inc['entidad']} no permite transcripción digital: se hace por "
                         "correo electrónico o con personal de la entidad (5.2).")
    if inc["estado"] == estados.RECHAZADA and not repo.rechazo_subsanado(inc_id):
        raise flujo.FlujoError("Primero debe subsanarse la causal del rechazo (módulo de seguimiento).")
    fecha = a_fecha(fecha_transcripcion)
    fuera = bool(info["fecha_limite"] and fecha > info["fecha_limite"])
    repo.insertar_transcripcion({
        "incapacidad_id": inc_id, "fecha": fecha.isoformat(), "medio": medio,
        "radicado": radicado.strip(), "evidencia": evidencia.strip(),
        "fuera_de_plazo": int(fuera), "nota": nota.strip(), "usuario": usuario})
    flujo.cambiar_estado(inc_id, estados.TRANSCRITA, usuario,
                         f"{medio}" + (" (fuera de plazo)" if fuera else ""), fecha=fecha)
    return {"fuera_de_plazo": fuera, "fecha_limite": info["fecha_limite"]}


def historial(inc_id: int) -> list[dict]:
    return repo.historial(inc_id)
