"""
Ajustes generales del proyecto.

Los demás módulos leen siempre `settings.X` en el momento de usarlo
(no copian el valor al importar), así las pruebas pueden cambiar las rutas.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
ARCHIVOS_DIR = BASE_DIR / "archivos_digitales"
REPORTES_DIR = BASE_DIR / "reportes"
PLANTILLAS_DIR = BASE_DIR / "plantillas"
ENV_FILE = BASE_DIR / ".env"      # credenciales del correo de envío (NO se sube a Git)
DB_PATH = Path(os.environ.get("INCAPACIDADES_DB", DATA_DIR / "incapacidades.db"))

# El procedimiento original trae el nombre de la empresa sin completar ("xxxxxxx S.A.")
NOMBRE_EMPRESA = "XXXXXXX S.A."

# Canales de recepción (5.1.1)
CANALES_RECEPCION = [
    "Recepción",
    "Oficinas principales",
    "Líderes comerciales",
    "Correo electrónico",
]

# Entidades mencionadas en el procedimiento (5.2 y tabla 5.2.1)
ENTIDADES = [
    "Salud Total",
    "Nueva EPS",
    "SOS",
    "Sanitas",
    "SURA EPS",
    "Asmet Salud",
    "Famisanar",
    "ARL SURA",
    "Otra",
]

# Medios de transcripción (5.2)
MEDIO_PORTAL = "Portal de la entidad"
MEDIO_CORREO = "Correo electrónico"
MEDIO_PRESENCIAL = "Presencial en la entidad"
MEDIOS_TRANSCRIPCION = [MEDIO_PORTAL, MEDIO_CORREO, MEDIO_PRESENCIAL]

# Días festivos adicionales (formato "AAAA-MM-DD") para el cálculo de días hábiles.
# Los festivos de Colombia se toman de la librería `holidays` si está instalada.
FESTIVOS_EXTRA: set[str] = set()

# Correos de destino de las notificaciones (completar con los reales)
CORREO_ADMON_PERSONAL = "administracion.personal@example.com"
CORREO_SG_SST = "sgsst@example.com"
CORREO_CONTABILIDAD = "contabilidad@example.com"
