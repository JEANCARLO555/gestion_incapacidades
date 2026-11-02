"""Avisos del monitoreo a EPS, ARL, AFP y trabajador (se guardan en la bandeja de notificaciones)."""
from config import reglas_monitoreo as rm
from core import notificaciones


def notificar_concepto_no_expedido(caso: dict, dias: int, usuario: str) -> int:
    asunto = f"Concepto de rehabilitación no expedido - {caso['colaborador']}"
    cuerpo = (f"El colaborador {caso['colaborador']} lleva {dias} días acumulados de incapacidad "
              f"temporal y no se ha expedido el concepto de rehabilitación (debía emitirse antes "
              f"del día {rm.DIA_LIMITE_SOLICITUD_CONCEPTO_EPS}). Se solicita su pronta expedición.")
    n = 0
    for tipo in ("EPS", "ARL", "AFP", "Trabajador"):
        destino = caso["colaborador"] if tipo == "Trabajador" else f"{tipo} ({caso['entidad']})" if tipo == "EPS" else tipo
        notificaciones.crear("Monitoreo-No expedido", tipo, destino, asunto, cuerpo,
                             caso["ultima_id"], usuario=usuario)
        n += 1
    return n


def comunicar_resultado(caso: dict, resultado: str, usuario: str) -> int:
    asunto = f"Concepto de rehabilitación: {resultado.lower()}"
    cuerpo = (f"Estimado(a) {caso['colaborador']}: le informamos que el concepto de "
              f"rehabilitación emitido por su EPS es {resultado.upper()}.")
    return notificaciones.crear("Monitoreo-Resultado", "Trabajador", caso["colaborador"],
                                asunto, cuerpo, caso["ultima_id"], usuario=usuario)


def comunicar_suspension_pago(caso: dict, dias: int, usuario: str) -> int:
    asunto = f"Suspensión del pago de la incapacidad por nómina - {caso['colaborador']}"
    cuerpo = (f"Estimado(a) {caso['colaborador']}: su incapacidad supera los "
              f"{rm.DIA_SUSPENSION_PAGO_NOMINA} días ({dias} acumulados). El pago por nómina se "
              "suspende y el reconocimiento debe gestionarlo usted ante el fondo de pensiones o la EPS.")
    return notificaciones.crear("Monitoreo-Suspensión", "Trabajador", caso["colaborador"],
                                asunto, cuerpo, caso["ultima_id"], usuario=usuario)
