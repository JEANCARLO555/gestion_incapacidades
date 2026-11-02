"""
Concepto de rehabilitación (5.5.3).

  - La EPS debe emitirlo antes de cumplirse el día 120 de incapacidad temporal.
  - Debe enviarse a la AFP antes de cumplirse el día 150.
  - Si no se expidió, se notifica a la EPS, ARL, AFP y al trabajador.
  - Se comunica el resultado (favorable / desfavorable) al trabajador.
"""
from config import reglas_monitoreo as rm


def pendiente_de(concepto: dict | None, dias: int) -> dict:
    """Qué debe hacer ahora el auxiliar con este caso. Urgencia: 0 nada, 1 aviso, 2 urgente, 3 vencido."""
    ant = rm.DIAS_ANTICIPACION_ALERTA
    emitido = bool(concepto and concepto.get("fecha_emision"))
    enviado = bool(concepto and concepto.get("fecha_envio_afp"))
    comunicado = bool(concepto and concepto.get("fecha_comunicacion_trabajador"))

    if emitido and enviado and comunicado:
        return {"accion": "Cumplido", "urgencia": 0, "mensaje": "Concepto emitido, enviado a la AFP y comunicado."}
    if not emitido:
        if dias > rm.DIA_LIMITE_SOLICITUD_CONCEPTO_EPS:
            return {"accion": "Notificar que no se expidió", "urgencia": 3,
                    "mensaje": "Pasó el día 120 sin concepto: notificar a EPS, ARL, AFP y trabajador."}
        if dias > rm.DIA_LIMITE_SOLICITUD_CONCEPTO_EPS - ant:
            return {"accion": "Solicitar concepto a la EPS", "urgencia": 2 if not (concepto and concepto.get("fecha_solicitud")) else 1,
                    "mensaje": f"Se acerca el día {rm.DIA_LIMITE_SOLICITUD_CONCEPTO_EPS}."}
        return {"accion": "Sin acción todavía", "urgencia": 0, "mensaje": ""}
    if not enviado:
        if dias > rm.DIA_LIMITE_ENVIO_AFP:
            return {"accion": "Enviar a la AFP (vencido)", "urgencia": 3,
                    "mensaje": f"Pasó el día {rm.DIA_LIMITE_ENVIO_AFP} sin enviar el concepto a la AFP."}
        return {"accion": "Enviar concepto a la AFP", "urgencia": 2,
                "mensaje": f"Debe enviarse antes del día {rm.DIA_LIMITE_ENVIO_AFP}."}
    return {"accion": "Comunicar resultado al trabajador", "urgencia": 2,
            "mensaje": f"Resultado: {concepto.get('resultado')}."}
