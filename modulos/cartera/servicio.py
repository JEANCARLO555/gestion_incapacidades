"""
Cartera (5.4.1 y paso 15).

Orden que fija el procedimiento:
  1. El auxiliar hace mínimo DOS requerimientos de cobro persuasivo.
  2. Si pasan 180 días de cobro sin pago (o hay evidencia de deterioro crediticio
     de la entidad) se traslada a Cartera.
  3. Agotadas las gestiones de Cartera, pasa a Jurídica.
"""
from datetime import date

from config import estados, plazos_eps
from core import auditoria, consultas, flujo, notificaciones
from core.utils import a_fecha, moneda, sumar_meses
from modulos.cartera import repositorio as repo

ETAPA_PERSUASIVO = "Cobro persuasivo"
ETAPA_CARTERA = "Cartera"
TIPO_REQUERIMIENTO = "Requerimiento persuasivo"
TIPO_ACUERDO = "Acuerdo de pago"
TIPO_GESTION_CARTERA = "Gestión de cartera"
MIN_REQUERIMIENTOS = 2
DIAS_PARA_CARTERA = 180
DIAS_ALERTA_PRESCRIPCION = 180   # avisar cuando falten menos de 180 días para los 3 años


def _fecha_cobro(inc: dict) -> date | None:
    return flujo.fecha_en_estado(inc["id"], estados.COBRADA)


def _limite_pago(inc: dict) -> date | None:
    base = flujo.fecha_en_estado(inc["id"], estados.TRANSCRITA)
    return sumar_meses(base, 12 * plazos_eps.LIMITE_PAGO_ENTIDAD_ANIOS) if base else None


def candidatas(hoy: date | None = None) -> list[dict]:
    hoy = hoy or date.today()
    filas = []
    for inc in consultas.listar_incapacidades(estados=[estados.COBRADA, estados.EN_CARTERA],
                                              orden="i.fecha_inicio, i.id"):
        cobro = _fecha_cobro(inc)
        promesa = a_fecha(inc["fecha_promesa_pago"])
        limite = _limite_pago(inc)
        esperado = consultas.resumen_liquidacion(inc["id"])
        filas.append({
            **inc, "fecha_cobro": cobro.isoformat() if cobro else None,
            "dias_desde_cobro": (hoy - cobro).days if cobro else None,
            "en_mora": bool(promesa and hoy > promesa),
            "requerimientos": repo.contar_gestiones(inc["id"], TIPO_REQUERIMIENTO),
            "gestiones_cartera": repo.contar_gestiones(inc["id"], TIPO_GESTION_CARTERA),
            "pendiente": (esperado["valor_eps"] - consultas.pagado_a_incapacidad(inc["id"]))
            if esperado["aplica"] else None,
            "vence_3_anios": limite.isoformat() if limite else None,
            "riesgo_prescripcion": bool(limite and (limite - hoy).days <= DIAS_ALERTA_PRESCRIPCION)})
    return filas


def _requiere_estado(inc_id: int, *permitidos: str) -> dict:
    inc = consultas.obtener_incapacidad(inc_id)
    if not inc or inc["estado"] not in permitidos:
        raise flujo.FlujoError("Estado no válido para esta acción: debe estar en " + " o ".join(permitidos) + ".")
    return inc


def generar_requerimiento(inc_id: int, usuario="sistema") -> str:
    """Texto del requerimiento de cobro persuasivo (plantilla) y registro de la gestión."""
    inc = _requiere_estado(inc_id, estados.COBRADA)
    numero = repo.contar_gestiones(inc_id, TIPO_REQUERIMIENTO) + 1
    resumen = consultas.resumen_liquidacion(inc_id)
    pendiente = (resumen["valor_eps"] - consultas.pagado_a_incapacidad(inc_id)) if resumen["aplica"] else None
    texto = notificaciones.render_plantilla(
        "requerimiento_cobro", numero=numero, colaborador=inc["colaborador"],
        documento=inc["documento"], entidad=inc["entidad"], tipo=inc["tipo"].lower(),
        fecha_inicio=inc["fecha_inicio"], fecha_fin=inc["fecha_fin"], dias=inc["dias"],
        valor_pendiente=moneda(pendiente) if pendiente is not None else "por determinar",
        fecha_cobro=(_fecha_cobro(inc) or "—"))
    notificaciones.crear("Cartera", "Entidad", inc["entidad"], f"Requerimiento de pago No. {numero}",
                         texto, inc_id, usuario=usuario)
    flujo.registrar_gestion(inc_id, ETAPA_PERSUASIVO, TIPO_REQUERIMIENTO,
                            f"Requerimiento No. {numero} generado", usuario)
    return texto


def registrar_requerimiento(inc_id: int, detalle: str, usuario="sistema", fecha=None) -> int:
    """Registra un requerimiento hecho por otro medio (llamada, correo propio...)."""
    _requiere_estado(inc_id, estados.COBRADA)
    return flujo.registrar_gestion(inc_id, ETAPA_PERSUASIVO, TIPO_REQUERIMIENTO,
                                   detalle or "Requerimiento de cobro", usuario, fecha)


def registrar_acuerdo_pago(inc_id: int, fecha_promesa, detalle: str, usuario="sistema") -> None:
    """5.4.1: acuerdo con los representantes de la entidad para el reconocimiento."""
    _requiere_estado(inc_id, estados.COBRADA, estados.EN_CARTERA)
    promesa = a_fecha(fecha_promesa)
    if not promesa:
        raise ValueError("Indique la nueva fecha de pago acordada.")
    repo.actualizar_incapacidad(inc_id, {"fecha_promesa_pago": promesa.isoformat()})
    flujo.registrar_gestion(inc_id, ETAPA_PERSUASIVO, TIPO_ACUERDO,
                            f"{detalle} (pago acordado para {promesa})", usuario)


def marcar_deterioro_crediticio(inc_id: int, evidencia: str, usuario="sistema") -> None:
    """Evidencia objetiva: la entidad se declara insolvente, entra en liquidación, etc."""
    _requiere_estado(inc_id, estados.COBRADA)
    if not evidencia.strip():
        raise ValueError("Describa la evidencia del deterioro de las condiciones crediticias.")
    repo.actualizar_incapacidad(inc_id, {"deterioro_crediticio": 1})
    flujo.registrar_gestion(inc_id, ETAPA_PERSUASIVO, "Deterioro crediticio", evidencia.strip(), usuario)


def trasladar_a_cartera(inc_id: int, usuario="sistema", hoy: date | None = None,
                        forzar: bool = False, justificacion: str = "") -> None:
    hoy = hoy or date.today()
    inc = _requiere_estado(inc_id, estados.COBRADA)
    if not forzar:
        n = repo.contar_gestiones(inc_id, TIPO_REQUERIMIENTO)
        if n < MIN_REQUERIMIENTOS:
            raise flujo.FlujoError(f"Se necesitan mínimo {MIN_REQUERIMIENTOS} requerimientos de cobro "
                                   f"persuasivo (hay {n}).")
        cobro = _fecha_cobro(inc)
        dias = (hoy - cobro).days if cobro else 0
        if dias < DIAS_PARA_CARTERA and not inc["deterioro_crediticio"]:
            raise flujo.FlujoError(f"Solo se traslada tras {DIAS_PARA_CARTERA} días de cobro sin pago "
                                   f"(van {dias}) o con evidencia de deterioro crediticio.")
    elif not justificacion.strip():
        raise ValueError("Para saltar las condiciones debe escribir una justificación.")
    flujo.cambiar_estado(inc_id, estados.EN_CARTERA, usuario,
                         "Traslado forzado: " + justificacion if forzar else "Traslado a cartera")
    if forzar:
        auditoria.registrar(usuario, "traslado forzado a cartera", "incapacidad", inc_id, justificacion)


def registrar_gestion_cartera(inc_id: int, detalle: str, usuario="sistema") -> int:
    _requiere_estado(inc_id, estados.EN_CARTERA)
    if not detalle.strip():
        raise ValueError("Describa la gestión de cartera.")
    return flujo.registrar_gestion(inc_id, ETAPA_CARTERA, TIPO_GESTION_CARTERA, detalle.strip(), usuario)


def escalar_a_juridico(inc_id: int, usuario="sistema") -> None:
    _requiere_estado(inc_id, estados.EN_CARTERA)
    if repo.contar_gestiones(inc_id, TIPO_GESTION_CARTERA) < 1:
        raise flujo.FlujoError("Cartera debe registrar al menos una gestión de cobro antes de pasar a Jurídica.")
    flujo.cambiar_estado(inc_id, estados.EN_JURIDICO, usuario, "Gestiones de cartera agotadas")


def bitacora(inc_id: int) -> list[dict]:
    return consultas.gestiones_de(inc_id)
