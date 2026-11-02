"""Hitos de monitoreo de incapacidades prolongadas (5.5.3)."""
from config import reglas_documentos as rd

HITOS = (90, 120, 150, 180)

DIA_LIMITE_SOLICITUD_CONCEPTO_EPS = 120   # el concepto de rehabilitación se pide antes del día 120
DIA_LIMITE_ENVIO_AFP = 150                # y se envía a la AFP antes del día 150
DIA_SUSPENSION_PAGO_NOMINA = 180          # después del 180 se suspende el pago por nómina

# Con cuántos días de anticipación se muestra una alerta (valor propuesto, ajustable)
DIAS_ANTICIPACION_ALERTA = 15

# Licencias de maternidad/paternidad no entran en el monitoreo de incapacidad prolongada
TIPOS_EXCLUIDOS_MONITOREO = {rd.TIPO_LICENCIA_MATERNIDAD, rd.TIPO_LICENCIA_PATERNIDAD}

RESULTADOS_CONCEPTO = ["Favorable", "Desfavorable"]
