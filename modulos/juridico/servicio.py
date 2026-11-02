"""
Cobro jurídico (5.4.2 y paso 15.3).

Casos que aplican: incapacidades negadas con causal improcedente, e incapacidades
aprobadas que incumplen el tiempo prometido de pago. Primera medida: derecho de
petición. Si la entidad no responde, última opción: acción de tutela.
Al final, el área jurídica decide si se recupera o se da de baja.
"""
from datetime import date

from config import estados, settings
from core import consultas, flujo, notificaciones
from core.utils import a_fecha, dias_habiles_entre
from modulos.juridico import repositorio as repo

ETAPA = "Jurídico"
TIPO_PETICION = "Derecho de petición"
TIPO_TUTELA = "Acción de tutela"
TIPO_DECISION = "Decisión"

# Supuesto: término de respuesta de un derecho de petición. El procedimiento no lo
# fija; 15 días hábiles es el término general de la Ley 1755 de 2015. Confirmar con Jurídica.
DIAS_HABILES_RESPUESTA = 15


def elegibles(hoy: date | None = None) -> list[dict]:
    """Casos que pueden abrirse como cobro jurídico y los que ya están en jurídico."""
    hoy = hoy or date.today()
    filas = []
    for inc in consultas.listar_incapacidades(
            estados=[estados.RECHAZADA, estados.COBRADA, estados.EN_JURIDICO], orden="i.fecha_inicio, i.id"):
        if inc["estado"] == estados.RECHAZADA and repo.rechazo_improcedente(inc["id"]):
            filas.append({**inc, "motivo": "Rechazo con causal improcedente"})
        elif inc["estado"] == estados.COBRADA:
            promesa = a_fecha(inc["fecha_promesa_pago"])
            if promesa and hoy > promesa:
                filas.append({**inc, "motivo": "Incumplió el tiempo de pago prometido"})
        elif inc["estado"] == estados.EN_JURIDICO:
            filas.append({**inc, "motivo": "En cobro jurídico"})
    return filas


def abrir_caso(inc_id: int, usuario="sistema", hoy: date | None = None) -> None:
    ok = {f["id"] for f in elegibles(hoy) if f["estado"] != estados.EN_JURIDICO}
    if inc_id not in ok:
        raise flujo.FlujoError("El caso no cumple las condiciones de cobro jurídico (5.4.2).")
    flujo.cambiar_estado(inc_id, estados.EN_JURIDICO, usuario, "Apertura de cobro jurídico")


def radicar_derecho_peticion(inc_id: int, fecha, radicado: str, usuario="sistema", motivo="") -> str:
    inc = _en_juridico(inc_id)
    texto = notificaciones.render_plantilla(
        "derecho_peticion", colaborador=inc["colaborador"], documento=inc["documento"],
        entidad=inc["entidad"], tipo=inc["tipo"].lower(), fecha_inicio=inc["fecha_inicio"],
        fecha_fin=inc["fecha_fin"], dias=inc["dias"], motivo=motivo or "Cobro de prestación económica")
    notificaciones.crear("Jurídico", "Entidad", inc["entidad"], "Derecho de petición", texto,
                         inc_id, usuario=usuario)
    flujo.registrar_gestion(inc_id, ETAPA, TIPO_PETICION, motivo or "Derecho de petición radicado",
                            usuario, fecha, radicado.strip() or None)
    return texto


def _peticiones_sin_respuesta(inc_id: int) -> list[dict]:
    return [g for g in consultas.gestiones_de(inc_id, tipo=TIPO_PETICION) if not g["respondida"]]


def registrar_respuesta(gestion_id: int, usuario="sistema") -> None:
    if not repo.obtener_gestion(gestion_id):
        raise ValueError("Gestión no encontrada.")
    repo.marcar_respondida(gestion_id)


def estado_peticion(inc_id: int, hoy: date | None = None) -> dict:
    hoy = hoy or date.today()
    pendientes = _peticiones_sin_respuesta(inc_id)
    if not pendientes:
        return {"hay_pendiente": False, "dias_habiles": None, "vencida": False}
    dias = dias_habiles_entre(a_fecha(pendientes[-1]["fecha"]), hoy)
    return {"hay_pendiente": True, "dias_habiles": dias, "vencida": dias >= DIAS_HABILES_RESPUESTA}


def radicar_tutela(inc_id: int, fecha, radicado: str, usuario="sistema", hoy: date | None = None) -> None:
    """Última opción: solo si hubo derecho de petición y la entidad no respondió a tiempo."""
    _en_juridico(inc_id)
    est = estado_peticion(inc_id, hoy)
    if not est["hay_pendiente"]:
        raise flujo.FlujoError("Primero debe radicarse un derecho de petición sin respuesta.")
    if not est["vencida"]:
        raise flujo.FlujoError(f"La entidad aún está dentro del término de respuesta "
                               f"(van {est['dias_habiles']} de {DIAS_HABILES_RESPUESTA} días hábiles).")
    flujo.registrar_gestion(inc_id, ETAPA, TIPO_TUTELA, "Acción de tutela exigiendo el pago",
                            usuario, fecha, radicado.strip() or None)


def decidir(inc_id: int, decision: str, justificacion: str, usuario="sistema") -> None:
    """El área jurídica decide si se recupera o se da de baja (paso 15.3)."""
    _en_juridico(inc_id)
    if decision not in ("Recuperar", "Dar de baja"):
        raise ValueError("La decisión debe ser «Recuperar» o «Dar de baja».")
    if not justificacion.strip():
        raise ValueError("Escriba la justificación de la decisión.")
    flujo.registrar_gestion(inc_id, ETAPA, TIPO_DECISION, f"{decision}: {justificacion.strip()}", usuario)
    if decision == "Dar de baja":
        flujo.cambiar_estado(inc_id, estados.DADA_DE_BAJA, usuario, justificacion.strip())


def _en_juridico(inc_id: int) -> dict:
    inc = consultas.obtener_incapacidad(inc_id)
    if not inc or inc["estado"] != estados.EN_JURIDICO:
        raise flujo.FlujoError("La incapacidad debe estar «En jurídico».")
    return inc


def bitacora(inc_id: int) -> list[dict]:
    return consultas.gestiones_de(inc_id)
