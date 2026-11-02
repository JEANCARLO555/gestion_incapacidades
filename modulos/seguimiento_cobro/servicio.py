"""
Seguimiento del cobro (5.4 y pasos 8 a 11).

Estados que maneja: Transcrita -> Cobrada o Rechazada -> Pagada.
El auxiliar revisa a diario el estado y deja evidencia de la gestión semanal.
"""
from datetime import date, timedelta

from config import estados
from core import auditoria, consultas, flujo
from core.utils import a_fecha
from modulos.seguimiento_cobro import repositorio as repo

ETAPA = "Seguimiento"
TIPO_SEGUIMIENTO = "Seguimiento semanal"
DIAS_ENTRE_SEGUIMIENTOS = 7


def panel() -> list[dict]:
    return repo.conteo_por_estado()


def en_gestion() -> list[dict]:
    return consultas.listar_incapacidades(
        estados=[estados.TRANSCRITA, estados.COBRADA, estados.RECHAZADA,
                 estados.EN_CARTERA, estados.EN_JURIDICO],
        orden="i.fecha_inicio, i.id")


def marcar_cobrada(inc_id: int, fecha_promesa_pago, usuario="sistema", fecha_cobro=None,
                   nota="") -> None:
    """Paso 8: la entidad aceptó la incapacidad y dio el tiempo de pago."""
    promesa = a_fecha(fecha_promesa_pago)
    if not promesa:
        raise ValueError("Indique la fecha en que la entidad prometió pagar.")
    flujo.cambiar_estado(inc_id, estados.COBRADA, usuario, nota, fecha=fecha_cobro)
    repo.actualizar_promesa_pago(inc_id, promesa.isoformat())


def marcar_rechazada(inc_id: int, causal: str, improcedente: bool, usuario="sistema",
                     fecha=None) -> int:
    """La entidad no admitió la información o documentación."""
    if not causal.strip():
        raise ValueError("Indique la causal del rechazo.")
    flujo.cambiar_estado(inc_id, estados.RECHAZADA, usuario, causal, fecha=fecha)
    return repo.insertar_rechazo({
        "incapacidad_id": inc_id, "fecha": (a_fecha(fecha) or date.today()).isoformat(),
        "causal": causal.strip(), "improcedente": int(improcedente), "usuario": usuario})


def subsanar_rechazo(inc_id: int, usuario="sistema") -> None:
    """El auxiliar validó la causal y subsanó el evento: ya se puede transcribir de nuevo."""
    inc = consultas.obtener_incapacidad(inc_id)
    if not inc or inc["estado"] != estados.RECHAZADA:
        raise flujo.FlujoError("La incapacidad no está rechazada.")
    rechazo = repo.ultimo_rechazo(inc_id)
    if not rechazo:
        raise flujo.FlujoError("No hay un rechazo registrado.")
    if rechazo["improcedente"]:
        raise flujo.FlujoError("Es un rechazo improcedente: va a cobro jurídico, no se subsana.")
    repo.marcar_subsanado(rechazo["id"])
    auditoria.registrar(usuario, "subsanar rechazo", "incapacidad", inc_id, rechazo["causal"])


def marcar_pagada(inc_id: int, usuario="sistema", fecha=None, nota="") -> None:
    flujo.cambiar_estado(inc_id, estados.PAGADA, usuario, nota, fecha=fecha)


def registrar_seguimiento(inc_id: int, detalle: str, usuario="sistema", fecha=None) -> int:
    """Deja la evidencia documental de la gestión semanal (pasos 9 y 11)."""
    if not detalle.strip():
        raise ValueError("Describa la gestión realizada.")
    return flujo.registrar_gestion(inc_id, ETAPA, TIPO_SEGUIMIENTO, detalle.strip(), usuario, fecha)


def pendientes_seguimiento(hoy: date | None = None) -> list[dict]:
    """Incapacidades sin seguimiento en los últimos 7 días."""
    hoy = hoy or date.today()
    filas = []
    for inc in consultas.listar_incapacidades(
            estados=[estados.TRANSCRITA, estados.COBRADA], orden="i.fecha_inicio, i.id"):
        ultima = repo.ultima_gestion(inc["id"], TIPO_SEGUIMIENTO)
        ultima_fecha = a_fecha(ultima["fecha"]) if ultima else None
        if ultima_fecha is None or hoy - ultima_fecha >= timedelta(days=DIAS_ENTRE_SEGUIMIENTOS):
            filas.append({**inc, "ultimo_seguimiento": ultima_fecha.isoformat() if ultima_fecha else "Nunca"})
    return filas


def bitacora(inc_id: int) -> list[dict]:
    return consultas.gestiones_de(inc_id)
