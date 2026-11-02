"""
Roles y protección de datos de salud.

IMPORTANTE: esta versión NO tiene inicio de sesión real. El rol se elige en la
barra lateral. Sirve para separar lo que cada persona ve, pero antes de usarlo
con datos reales hay que conectar un login (por ejemplo el de la empresa).
"""
from dataclasses import dataclass

from config import responsables as resp

ROL_RECEPCIONISTA = "Recepcionista"
ROL_AUXILIAR = "Auxiliar de administración de personal"
ROL_COORDINACION = "Coordinación de administración de personal"
ROL_LIDER = "Líder"
ROL_CONTABILIDAD = "Contabilidad"
ROL_CARTERA = "Cartera"
ROL_JURIDICA = "Jurídica"
ROL_SST = "SG-SST"

ROLES = [ROL_RECEPCIONISTA, ROL_AUXILIAR, ROL_COORDINACION, ROL_LIDER,
         ROL_CONTABILIDAD, ROL_CARTERA, ROL_JURIDICA, ROL_SST]

# Cómo se llama cada rol de la aplicación en la columna «Responsable» de la tabla 7 del procedimiento.
# Coordinación y SG-SST no aparecen en esa columna (ver DESCRIPCION_ROL).
RESPONSABLE_EN_PROCEDIMIENTO = {
    ROL_RECEPCIONISTA: resp.RECEPCIONISTA, ROL_AUXILIAR: resp.AUXILIAR, ROL_LIDER: resp.LIDER,
    ROL_CONTABILIDAD: resp.CONTABILIDAD, ROL_CARTERA: resp.CARTERA, ROL_JURIDICA: resp.JURIDICA,
}

# (qué hace en la aplicación, de dónde sale en el procedimiento)
DESCRIPCION_ROL = {
    ROL_RECEPCIONISTA: ("Recibe la incapacidad y los documentos y los registra.",
                        "Paso 4 de la tabla 7 y canal «Recepción» (5.1.1)."),
    ROL_AUXILIAR: ("Verifica, transcribe, cobra, concilia y archiva. Es quien tiene más pasos.",
                   "Pasos 4 a 16 de la tabla 7."),
    ROL_COORDINACION: ("Supervisa: ve todo lo del auxiliar, ve la auditoría y puede saltarse reglas de "
                       "traslado a cartera con justificación.",
                       "Se nombra en el texto de 5.1.2 (cita al colaborador) y 5.4.1 (acuerdos con las "
                       "entidades); NO aparece en la columna Responsable."),
    ROL_LIDER: ("Asigna el reemplazo y ve solo las incapacidades de su equipo.", "Paso 2 de la tabla 7."),
    ROL_CONTABILIDAD: ("Registra lo que las entidades consignaron.", "Paso 13 de la tabla 7."),
    ROL_CARTERA: ("Gestiona el cobro de las incapacidades trasladadas a cartera.", "Paso 15 de la tabla 7."),
    ROL_JURIDICA: ("Derecho de petición, tutela y decisión de recuperar o dar de baja.",
                   "Paso 15 de la tabla 7 y sección 5.4.2."),
    ROL_SST: ("Solo consulta el reporte de ausentismo.",
              "Paso 6: es quien RECIBE el reporte, no un responsable de la tabla."),
}


@dataclass(frozen=True)
class Sesion:
    usuario: str
    rol: str


_ADMON = {ROL_AUXILIAR, ROL_COORDINACION}

# Qué roles pueden abrir cada módulo
PERMISOS_MODULO = {
    "recepcion": {ROL_RECEPCIONISTA, ROL_LIDER} | _ADMON,
    "verificacion": _ADMON,
    "transcripcion": _ADMON,
    "liquidacion": _ADMON | {ROL_CONTABILIDAD},
    "monitoreo": _ADMON,
    "seguimiento_cobro": _ADMON,
    "cartera": _ADMON | {ROL_CARTERA, ROL_JURIDICA},
    "juridico": {ROL_COORDINACION, ROL_JURIDICA},
    "conciliacion": _ADMON | {ROL_CONTABILIDAD},
    "nomina": _ADMON,
    "ausentismo": _ADMON | {ROL_SST},
    "archivo": _ADMON,
    "ia": _ADMON,
}

# Columnas que cada rol NO debe ver
COLUMNAS_OCULTAS = {
    ROL_LIDER: {"tipo", "observaciones", "ibc", "documento", "entidad"},
    ROL_RECEPCIONISTA: {"ibc"},
    ROL_SST: {"ibc", "observaciones", "documento"},
    ROL_JURIDICA: {"ibc"},
    ROL_CARTERA: {"ibc"},
}

ROLES_VEN_AUDITORIA = {ROL_COORDINACION}
ROLES_VEN_CLINICOS = _ADMON
# Cobro persuasivo (paso 15.1) lo hace la administración de personal; Cartera recibe después
ROLES_COBRO_PERSUASIVO = _ADMON


def puede_ver_modulo(rol: str, modulo: str) -> bool:
    return rol in PERMISOS_MODULO.get(modulo, set())


def puede_ver_datos_clinicos(rol: str) -> bool:
    return rol in ROLES_VEN_CLINICOS


def filtrar_columnas(df, rol: str):
    """Quita de un DataFrame las columnas que el rol no debe ver."""
    ocultas = COLUMNAS_OCULTAS.get(rol, set())
    return df.drop(columns=[c for c in df.columns if c in ocultas])
