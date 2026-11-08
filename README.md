# Gestión de incapacidades

Aplicación en Python (Streamlit + SQLite) que sigue el procedimiento **INCAPACIDADES v001**
de Gestión Humana: desde que llega la incapacidad hasta que se cobra, se concilia y se archiva.

## Cómo ejecutarla

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows   (en Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
streamlit run app.py
```

Se abre en el navegador. La base de datos se crea sola en `data/incapacidades.db`.

**Para probarla con datos ficticios** (nunca uses datos reales mientras pruebas):

```bash
python -m tests.datos_demo
```

**Para correr las pruebas automáticas:** `python -m pytest tests -q`

## Configurar el envío de correo (una sola vez)

La aplicación envía desde su propia cuenta (`soyvato91@gmail.com`). Los destinatarios se escriben en
la pantalla; no necesitan configurar nada.

1. Entra a https://myaccount.google.com/apppasswords con esa cuenta (requiere la verificación en dos
   pasos) y crea una **contraseña de aplicación** de 16 letras.
2. En la carpeta del proyecto: `Copy-Item .env.example .env`
3. Abre `.env` con el Bloc de notas y pega la contraseña en `SMTP_PASSWORD=`. Guarda.
4. Reinicia la app. En **Ausentismo SG-SST** escribe el correo destino y pulsa «Generar y enviar por correo».

El archivo `.env` contiene la contraseña: no lo compartas ni lo subas a Git (ya está en `.gitignore`).

## Estructura

| Carpeta | Qué contiene |
|---|---|
| `config/` | Las reglas del procedimiento: documentos por tipo, porcentajes de pago, hitos, plazos por EPS, estados. **Si el procedimiento cambia, se cambia aquí.** |
| `core/` | Lo compartido: base de datos, tablas, seguridad, notificaciones, auditoría, días hábiles, consultas y cambios de estado. |
| `modulos/<nombre>/` | Un módulo por carpeta, siempre con `interfaz.py` (pantallas), `servicio.py` (reglas) y `repositorio.py` (base de datos). |
| `plantillas/` | Textos base de los correos y documentos. |
| `tests/` | Pruebas automáticas y datos de demostración. |
| `data/`, `archivos_digitales/`, `reportes/` | Se llenan al usar la app. **Están fuera de Git.** |

Dos archivos que no estaban en la estructura original y se agregaron en `core/`:
`consultas.py` (lecturas que usan varios módulos) y `flujo.py` (cambio de estado con validación),
más `ui.py` (ayudas de pantalla). Así los módulos no se llaman entre sí.

## Roles y responsables

La columna «Responsable» de la tabla 7 del procedimiento nombra: Colaborador, Líder, Recepcionista,
Auxiliar de administración de personal, Contabilidad, Cartera, Jurídica y Gestión documental.
La aplicación tiene un rol para cada uno, **excepto** Colaborador y Gestión documental, cuyos pasos
(informar, entregar documentos, recibir el archivo físico) ocurren fuera de la aplicación.
Además hay dos roles que no están en esa columna: **Coordinación** (se nombra en el texto de 5.1.2 y 5.4.1)
y **SG-SST** (solo recibe el reporte de ausentismo).

La pantalla **📋 Proceso (16 pasos)** muestra la tabla completa con el módulo donde se hace cada paso, y cada
módulo trae el desplegable «¿Quién es responsable según el procedimiento?». La relación está en
`config/responsables.py` y los permisos en `core/seguridad.py`.

## Módulos y sección del procedimiento

| Módulo | Sección | Qué hace |
|---|---|---|
| `recepcion` | 5.1.1 | Registra colaboradores e incapacidades, canal de recepción, documentos entregados, prórrogas y reemplazo. |
| `verificacion` | 5.1.2 | Lista de chequeo, aviso al colaborador (3 días hábiles), segundo llamado, copia digital organizada. |
| `transcripcion` | 5.2 / 5.2.1 | Cola ordenada por plazo de cada EPS; registra radicado y evidencia. |
| `liquidacion` | 5.5.2 | 100 % empresa (días 1-2), 67 % EPS (3-90), 50 % EPS (91-180), día 181+ trámite del colaborador. |
| `monitoreo` | 5.5.3 | Reporte mensual 90/120/150/180, concepto de rehabilitación, comunicaciones, reintegros. |
| `seguimiento_cobro` | 5.4 | Transcrita → Cobrada / Rechazada → Pagada; seguimiento semanal con evidencia. |
| `cartera` | 5.4.1 y paso 15 | Requerimientos persuasivos (mínimo 2), acuerdos de pago, traslado a cartera, alerta de 3 años. |
| `juridico` | 5.4.2 | Derecho de petición → tutela → recuperar o dar de baja. |
| `conciliacion` | 5.5 | La EPS le paga a la empresa: se registra el pago, se asigna a la incapacidad (con los días pagados del detalle de la entidad), saldos por EPS y reporte mensual. |
| `nomina` | 5.2 | Novedades de nómina por mes (días y valores empresa / EPS). |
| `ausentismo` | paso 6 | Reporte mensual para el SG-SST (sin diagnósticos), con índice de ausentismo. |
| `archivo` | 5.3 / paso 16 | Lista de carpetas con los documentos escaneados (descargar y abrir la carpeta), archivo físico por entidad y fecha, verificación contra el pago, destrucción de documentos clínicos. |
| `ia` | nota final | Indicadores locales y, opcional, preguntas a un modelo de IA con datos anónimos. |

## ⚠️ Lo que debes saber antes de usarla con datos reales

1. **No tiene inicio de sesión.** El rol se elige a mano en la barra lateral. Separa lo que cada
   rol ve, pero no es seguridad real. Hay que conectarlo al login de la empresa.
2. **Datos de salud.** No guarda diagnósticos. La epicrisis es solo una casilla de "recibida", y las
   copias digitales clínicas se borran al archivar (paso 16). Aun así, valida con tu área jurídica el
   cumplimiento de la Ley 1581 de 2012 y protege la carpeta `data/` y `archivos_digitales/`.
3. **Envío de correos.** Está probado con un servidor *simulado*, no con Gmail real. Ver la sección
   «Configurar el envío de correo». Los correos de destino fijos (`CORREO_ADMON_PERSONAL`, etc.) en
   `config/settings.py` son de ejemplo.
4. **El módulo de IA con modelo no se probó contra la API real**, solo la parte local y el caso sin clave.
   Se activa con `ANTHROPIC_API_KEY`.
5. **Copias de seguridad.** Copia `data/incapacidades.db` con regularidad.

## Decisiones y supuestos (confirmar con Gestión Humana)

El procedimiento no lo dice todo. Esto es lo que se asumió; cada punto se cambia en un solo lugar:

- **Plazo de transcripción:** se cuenta desde la fecha de *inicio* de la incapacidad (en paternidad, desde el
  nacimiento). `config/plazos_eps.py`.
- **Entidades sin plazo** (Famisanar y «Otra»): la tabla 5.2.1 no las trae; se muestra «sin plazo definido».
- **Liquidación:** el 5.5.2 se aplica a *enfermedad general* y *accidente de tránsito* (origen común). Para
  *accidente laboral* y *licencias* el procedimiento no define el cálculo, así que **no se liquidan** (se avisa en pantalla).
  `config/reglas_pago.py`.
- **Valor diario** = IBC / 30. Es un cálculo de *ayuda*: en conciliación manda el detalle de pago de la entidad, por
  eso un pago se puede asignar aunque la incapacidad no tenga valor calculado (por ejemplo, IBC en $0).
- **Licencia de paternidad:** el 5.1.2 no pide certificado de incapacidad pero la regla general dice que el soporte es
  obligatorio en todos los casos. Se siguió la lista específica (sin certificado). `config/reglas_documentos.py`.
- **Documentación completa** = todos los documentos requeridos **y** la documentación física en Administración de personal.
- **Anticipación de alertas** de rehabilitación: 15 días. `config/reglas_monitoreo.py`.
- **Cartera:** requiere 2 requerimientos y (180 días de cobro o evidencia de deterioro crediticio). Un coordinador
  puede saltarse la regla con justificación (queda en auditoría).
- **Término de respuesta del derecho de petición:** 15 días hábiles (supuesto basado en la Ley 1755 de 2015; el
  procedimiento no lo fija). Confirmar con Jurídica. `modulos/juridico/servicio.py`.
- **Reintegros (>180 días):** se interpretó como el registro de los pagos que la EPS o el fondo hacen directamente al trabajador.
- **Festivos:** se toman de la librería `holidays` (Colombia). Se pueden sumar más en `FESTIVOS_EXTRA`.
- **Plantillas:** los «fundamentos de hecho y de derecho» quedan marcados para que los complete Jurídica.

## De dónde sale cada dinero (liquidación, nómina, conciliación)

Para una incapacidad de enfermedad general, **Liquidación** calcula tres valores:

| Valor | Qué es | Dónde se ve en la app |
|---|---|---|
| Total a pagar al trabajador (días 1 a 180) | Lo que se le paga por nómina | Liquidación y Novedades de nómina |
| Lo asume la empresa | Los 2 primeros días (100 %); no se cobra a nadie | Liquidación y Novedades de nómina |
| Lo debe reconocer la EPS | El resto hasta el día 180; se cobra a la entidad | Liquidación, Cartera y Conciliación |

**Conciliación no es el pago al trabajador**: es el dinero que la EPS consigna a la empresa. Del día 181 en
adelante no se paga por nómina; el trámite es del colaborador (5.5.2) y lo que llegue se anota en
Monitoreo → Reintegros. Supuesto a confirmar: la empresa paga al trabajador por nómina y luego cobra a la EPS su parte.

## Documentos escaneados

Se suben en **Verificación documental → Copia digital** y se guardan en
`archivos_digitales/<entidad>/<colaborador>_<fecha de inicio>/`. En **Archivo → 📁 Documentos escaneados** hay
una lista de esas carpetas (colaborador, entidad, número de archivos, última carga); al elegir una se ven sus
documentos con botón de descarga y, en Windows, el botón «Abrir la carpeta en el Explorador».
Solo aparecen los archivos subidos desde la aplicación. Las rutas se guardan relativas, así que se puede mover
el proyecto: hay que llevarse juntas las carpetas `data/` y `archivos_digitales/`.

## Pendiente / ideas siguientes

- Inicio de sesión real y permisos por usuario.
- Lectura automática de certificados (OCR) para llenar la recepción.
- Carga masiva de pagos desde el Excel de Contabilidad.
- Completar el nombre de la empresa (`NOMBRE_EMPRESA`) y los correos reales.


comandos para integrar modelo de IA

-instalar ollama desde la terminal de VS: irm https://ollama.com/install.ps1 | iex
-modelo de IA (Qwen 2.5) en la terminal pegar de VS: ollama run qwen2.5:1.5b
-Para salir cuando diga sucess: /exit

IMPORTANTE:
-ejecutar en la terminal: cd gestion_incapacidades
-ir al programa en la terminal: streamlit run app.py

CODIGOS:
la version= py -3.12 --versión

agregar para las lbrerias= py -3.12 -m venv .venv

agregar las librerias= .\.venv\Scripts\python -m pip install -r requirements.txt

correr la aplicasion= (.\.venv\Scripts\python -m streamlit run app.py)  (copiar lo que esta dentro del paréntesis)

este es para abrir el block de notas para enviar el correo
   Copy-Item .env.example .env
   notepad .env


pip uninstall pyarrow -y
pip install --force-reinstall pyarrow


pip install --force-reinstall -r requirements.txt

streamlit run app.py

INSTALAR PYTHON 3.12:   winget install Python.Python.3.12