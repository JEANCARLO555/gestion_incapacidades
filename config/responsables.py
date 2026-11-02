"""
Tabla «7. DESARROLLO» del procedimiento: cada paso, quién es el responsable y en qué
módulo de la aplicación se hace. Es la fuente de la pantalla «Proceso (16 pasos)» y de la
ayuda «¿Quién es responsable?» que aparece en cada módulo.
"""

COLABORADOR = "Colaborador"
LIDER = "Líder"
RECEPCIONISTA = "Recepcionista"
AUXILIAR = "Auxiliar de administración de personal"
CONTABILIDAD = "Contabilidad"
CARTERA = "Cartera"
JURIDICA = "Jurídica"
GESTION_DOCUMENTAL = "Gestión documental"

PASOS = [
    {"no": 1, "actividad": "Informar situación",
     "descripcion": "Informar de inmediato al jefe inmediato y a administración de personal la situación que "
                    "da lugar a la incapacidad o licencia.",
     "responsables": [COLABORADOR], "modulos": ["recepcion"],
     "en_app": "Lo hace el colaborador fuera de la aplicación. En «Recepción» se anota si informó al jefe."},
    {"no": 2, "actividad": "Asignar reemplazo",
     "descripcion": "Gestionar el reemplazo del colaborador que está incapacitado.",
     "responsables": [LIDER], "modulos": ["recepcion"],
     "en_app": "Recepción → Recibidas → «Asignar reemplazo»."},
    {"no": 3, "actividad": "Remitir incapacidad",
     "descripcion": "Enviar al líder y/o administración de personal la incapacidad (original y/o copia) y la "
                    "epicrisis o documento que la soporte, máximo 2 días después de conferida; en accidente de "
                    "tránsito, además el FURIPS.",
     "responsables": [COLABORADOR], "modulos": ["recepcion"],
     "en_app": "Lo hace el colaborador fuera de la aplicación. «Recepción» registra lo que entregó y por qué canal."},
    {"no": 4, "actividad": "Revisar documentación",
     "descripcion": "Recibir las incapacidades y la documentación, verificar que esté completa y corresponda, y "
                    "diligenciar el Formato de Seguimiento.",
     "responsables": [RECEPCIONISTA, AUXILIAR], "modulos": ["recepcion", "verificacion"],
     "en_app": "Recepción (recepcionista) y Verificación documental (auxiliar)."},
    {"no": 5, "actividad": "Transcripción de incapacidad",
     "descripcion": "Si se requiere transcripción, el auxiliar pide al colaborador los documentos; si no los "
                    "entrega, el colaborador hace el trámite directamente ante su EPS.",
     "responsables": [AUXILIAR, COLABORADOR], "modulos": ["verificacion", "transcripcion"],
     "en_app": "Verificación (pedir lo que falta) y Transcripción. El trámite directo del colaborador ocurre "
               "fuera de la aplicación."},
    {"no": 6, "actividad": "Remitir al SG-SST el reporte de ausentismo",
     "descripcion": "Enviar por correo al SG-SST el informe de ausentismos en los primeros 3 días de cada mes.",
     "responsables": [AUXILIAR], "modulos": ["ausentismo"],
     "en_app": "Ausentismo SG-SST → «Generar y enviar por correo»."},
    {"no": 7, "actividad": "Radicar ante las EPS las incapacidades",
     "descripcion": "Escanear el certificado y los documentos y radicar en la página web o en físico en la "
                    "EPS o ARL; dejar evidencia de la gestión.",
     "responsables": [AUXILIAR], "modulos": ["transcripcion"],
     "en_app": "Transcripción (radicado y evidencia)."},
    {"no": 8, "actividad": "Aceptación de la incapacidad y tiempo de pago",
     "descripcion": "La EPS o ARL notifica por los correos autorizados la aceptación y el tiempo para pagar.",
     "responsables": [AUXILIAR], "modulos": ["seguimiento_cobro"],
     "en_app": "Seguimiento de cobro → «Marcar como COBRADA» con la fecha prometida de pago."},
    {"no": 9, "actividad": "Cobro de la incapacidad",
     "descripcion": "Solicitar el pago de las prestaciones a la EPS o ARL cada semana, diligenciando sus "
                    "formularios; dejar evidencia.",
     "responsables": [AUXILIAR], "modulos": ["seguimiento_cobro"],
     "en_app": "Seguimiento de cobro → Seguimiento semanal."},
    {"no": 10, "actividad": "Pago de incapacidad",
     "descripcion": "Aceptada la solicitud, la EPS o ARL avisa por correo y paga por transferencia a la cuenta "
                    "que indique la Tesorería.",
     "responsables": [AUXILIAR], "modulos": ["seguimiento_cobro", "conciliacion"],
     "en_app": "Conciliación → Registrar pago; Seguimiento de cobro → «Marcar como PAGADA»."},
    {"no": 11, "actividad": "Seguimiento al trámite de cobro",
     "descripcion": "Seguimiento semanal por los canales de la EPS o ARL y registro de incapacidades, pagos y "
                    "saldos que adeudan; dejar evidencia.",
     "responsables": [AUXILIAR], "modulos": ["seguimiento_cobro", "conciliacion"],
     "en_app": "Seguimiento semanal y Conciliación → Saldos por entidad."},
    {"no": 12, "actividad": "Identificación de los pagos realizados por la EPS o ARL",
     "descripcion": "Solicitar el detalle de los pagos hechos por la EPS o ARL según el seguimiento de cobro.",
     "responsables": [AUXILIAR], "modulos": ["conciliacion"],
     "en_app": "Conciliación → Identificar pagos (el detalle se baja del portal de la entidad, fuera de la app)."},
    {"no": 13, "actividad": "Conciliación contable",
     "descripcion": "Contabilidad informa los valores consignados por EPS; el auxiliar identifica a qué "
                    "colaboradores pertenecen y envía la información por correo.",
     "responsables": [CONTABILIDAD, AUXILIAR], "modulos": ["conciliacion"],
     "en_app": "Conciliación → Registrar pago (Contabilidad) y Reporte mensual (auxiliar)."},
    {"no": 14, "actividad": "Falta de reconocimiento y pago de las prestaciones por parte de las EPS",
     "descripcion": "Si la EPS se niega a reconocer la incapacidad o licencia, se sigue el procedimiento del "
                    "paso 15.",
     "responsables": [AUXILIAR], "modulos": ["seguimiento_cobro"],
     "en_app": "Seguimiento de cobro → «Marcar como RECHAZADA»; luego Cartera o Jurídico."},
    {"no": 15, "actividad": "Cobro persuasivo de incapacidad o licencia",
     "descripcion": "Mínimo dos requerimientos de cobro persuasivo; a los 180 días de cobro (o con deterioro "
                    "crediticio de la entidad) se traslada a cartera; agotada la cartera pasa a jurídica, que "
                    "decide si se recupera o se da de baja.",
     "responsables": [AUXILIAR, CARTERA, JURIDICA], "modulos": ["cartera", "juridico"],
     "en_app": "Cartera (auxiliar y cartera) y Cobro jurídico (jurídica)."},
    {"no": 16, "actividad": "Archivo de incapacidades pagadas",
     "descripcion": "Identificado el pago, enviar la incapacidad a gestión documental; la historia clínica o "
                    "epicrisis se destruye y no reposa en el archivo.",
     "responsables": [AUXILIAR, GESTION_DOCUMENTAL], "modulos": ["archivo"],
     "en_app": "Archivo → Pagadas por depurar. La recepción física en Gestión documental ocurre fuera de la app."},
]

# Módulos que salen de secciones del procedimiento que NO tienen responsable en la tabla 7
SECCIONES_SIN_PASO = {
    "liquidacion": "5.5.2 Porcentajes de reconocimiento",
    "monitoreo": "5.5.3 Gestión de monitoreo de incapacidades",
    "nomina": "5.2 Novedades de nómina",
    "ia": "Nota final del procedimiento (análisis con inteligencia artificial)",
}

PROCESO_RESPONSABLE_GENERAL = ("La sección 4 del procedimiento dice que el proceso de Administración de "
                               "Personal vela por el cumplimiento de todo el documento.")


def pasos_de_modulo(clave: str) -> list[dict]:
    return [p for p in PASOS if clave in p["modulos"]]


def pasos_de_responsable(nombre: str) -> list[dict]:
    return [p for p in PASOS if nombre in p["responsables"]]


def nota_sin_pasos(clave: str) -> str:
    seccion = SECCIONES_SIN_PASO.get(clave, "")
    return (f"Este módulo sale de la sección «{seccion}», que no asigna un responsable en la tabla de "
            f"desarrollo. {PROCESO_RESPONSABLE_GENERAL}")
