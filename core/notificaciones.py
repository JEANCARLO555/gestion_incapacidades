"""
Notificaciones y envío de correos.

Hay dos formas de salir un correo:
  - Directo: `enviar_correo(...)` (por ejemplo el reporte de ausentismo con su Excel adjunto).
  - Bandeja: `crear(...)` deja la notificación como «Pendiente» y se envía con el botón
    «Enviar pendientes» de la pantalla Notificaciones.

La cuenta que ENVÍA se configura una sola vez en el archivo `.env` (ver `.env.example`):
    SMTP_USER=soyvato91@gmail.com
    SMTP_PASSWORD=<contraseña de aplicación de 16 letras>
Los destinatarios no necesitan configurar nada: se escriben en la pantalla.
"""
import json
import mimetypes
import os
import re
import smtplib
from contextlib import contextmanager
from email.message import EmailMessage
from pathlib import Path
from string import Template

from config import settings
from core import database as db
from core.utils import ahora_iso

mimetypes.add_type("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx")

MAX_DESTINATARIOS = 10
_RE_CORREO = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")


class CorreoError(Exception):
    """No se pudo enviar el correo (el mensaje explica por qué y qué hacer)."""


# ---------------------------------------------------------------- plantillas y bandeja
def render_plantilla(plantilla: str, /, **datos) -> str:
    """Carga plantillas/<plantilla>.txt y reemplaza los $campos."""
    texto = (settings.PLANTILLAS_DIR / f"{plantilla}.txt").read_text(encoding="utf-8")
    datos.setdefault("empresa", settings.NOMBRE_EMPRESA)
    return Template(texto).safe_substitute(**datos)


def crear(categoria: str, destinatario_tipo: str, destinatario: str, asunto: str, mensaje: str,
          incapacidad_id: int | None = None, correo: str | None = None,
          usuario: str = "sistema") -> int:
    return db.insert("notificaciones", {
        "incapacidad_id": incapacidad_id, "categoria": categoria,
        "destinatario_tipo": destinatario_tipo, "destinatario": destinatario,
        "correo": correo, "asunto": asunto, "mensaje": mensaje, "usuario": usuario})


def existe(incapacidad_id: int, categoria: str) -> bool:
    fila = db.fetch_one("SELECT id FROM notificaciones WHERE incapacidad_id = ? AND categoria = ? "
                        "LIMIT 1", (incapacidad_id, categoria))
    return fila is not None


def listar(estado: str | None = None, limite: int = 300) -> list[dict]:
    if estado:
        return db.fetch_all("SELECT * FROM notificaciones WHERE estado = ? ORDER BY id DESC LIMIT ?",
                            (estado, limite))
    return db.fetch_all("SELECT * FROM notificaciones ORDER BY id DESC LIMIT ?", (limite,))


def marcar_enviada(notificacion_id: int) -> None:
    db.update("notificaciones", notificacion_id, {"estado": "Enviada", "enviado_en": ahora_iso()})


# ---------------------------------------------------------------- destinatarios
def validar_correos(texto: str) -> list[str]:
    """Convierte 'a@x.com, b@y.com' en una lista validada y sin repetidos."""
    partes = [p for p in re.split(r"[,;\s]+", texto or "") if p]
    if not partes:
        raise ValueError("Escriba al menos un correo de destino.")
    invalidos = [p for p in partes if not _RE_CORREO.match(p)]
    if invalidos:
        raise ValueError("Correo(s) no válido(s): " + ", ".join(invalidos))
    unicos = list(dict.fromkeys(p.lower() for p in partes))
    if len(unicos) > MAX_DESTINATARIOS:
        raise ValueError(f"Máximo {MAX_DESTINATARIOS} destinatarios por envío.")
    return unicos


def _ruta_preferencias() -> Path:
    return settings.DB_PATH.parent / "preferencias.json"


def ultimos_destinatarios(clave: str = "ausentismo") -> str:
    try:
        return json.loads(_ruta_preferencias().read_text(encoding="utf-8")).get(clave, "")
    except (OSError, ValueError):
        return ""


def guardar_destinatarios(texto: str, clave: str = "ausentismo") -> None:
    try:
        datos = json.loads(_ruta_preferencias().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        datos = {}
    datos[clave] = texto
    _ruta_preferencias().parent.mkdir(parents=True, exist_ok=True)
    _ruta_preferencias().write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- configuración SMTP
def _leer_env_file() -> dict:
    datos = {}
    ruta = settings.ENV_FILE
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            datos[clave.strip()] = valor.strip().strip('"').strip("'")
    return datos


def configuracion_smtp() -> dict | None:
    """Lee la cuenta de envío (variables de entorno o archivo .env). None si falta."""
    archivo = _leer_env_file()

    def valor(nombre: str, defecto: str = "") -> str:
        return (os.environ.get(nombre) or archivo.get(nombre) or defecto).strip()

    usuario = valor("SMTP_USER")
    clave = valor("SMTP_PASSWORD").replace(" ", "")      # Google la muestra con espacios
    if not usuario or not clave:
        return None
    try:
        puerto = int(valor("SMTP_PORT", "465"))
    except ValueError:
        puerto = 465
    return {"host": valor("SMTP_HOST", "smtp.gmail.com"), "port": puerto, "usuario": usuario,
            "clave": clave, "remitente": valor("SMTP_FROM", usuario)}


def smtp_configurado() -> bool:
    return configuracion_smtp() is not None


@contextmanager
def _conexion():
    """Abre la sesión con el servidor de correo y traduce los errores a mensajes claros."""
    cfg = configuracion_smtp()
    if not cfg:
        raise CorreoError("El envío de correo no está configurado. Copie el archivo .env.example "
                          "como .env y escriba la contraseña de aplicación (ver README).")
    try:
        if cfg["port"] == 465:
            smtp = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=30)
        else:
            smtp = smtplib.SMTP(cfg["host"], cfg["port"], timeout=30)
            smtp.starttls()
        try:
            smtp.login(cfg["usuario"], cfg["clave"])
            yield smtp, cfg
        finally:
            try:
                smtp.quit()
            except Exception:
                pass
    except smtplib.SMTPAuthenticationError as e:
        raise CorreoError(
            f"{cfg['host']} rechazó el usuario o la contraseña. Con Gmail debe usar una «contraseña de "
            "aplicación» de 16 letras (no la contraseña normal) y tener activa la verificación en "
            "dos pasos.") from e
    except smtplib.SMTPRecipientsRefused as e:
        raise CorreoError("El servidor rechazó el correo de destino: " + ", ".join(e.recipients)) from e
    except smtplib.SMTPException as e:
        raise CorreoError(f"El servidor de correo respondió con un error: {e}") from e
    except OSError as e:
        raise CorreoError(f"No hay conexión con el servidor de correo ({cfg['host']}:{cfg['port']}). "
                          "Revise Internet o el firewall.") from e


def _mensaje(cfg: dict, destinatarios: list[str], asunto: str, cuerpo: str, adjuntos) -> EmailMessage:
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = cfg["remitente"], ", ".join(destinatarios), asunto
    msg.set_content(cuerpo)
    for ruta in adjuntos or []:
        ruta = Path(ruta)
        tipo = mimetypes.guess_type(ruta.name)[0] or "application/octet-stream"
        principal, sub = tipo.split("/", 1)
        msg.add_attachment(ruta.read_bytes(), maintype=principal, subtype=sub, filename=ruta.name)
    return msg


def enviar_correo(destinatarios: list[str], asunto: str, cuerpo: str, adjuntos=None) -> None:
    """Envía un correo ahora mismo. Lanza CorreoError con el motivo si no se pudo."""
    with _conexion() as (smtp, cfg):
        smtp.send_message(_mensaje(cfg, destinatarios, asunto, cuerpo, adjuntos))


def enviar_pendientes() -> dict:
    """Envía las notificaciones «Pendiente» de la bandeja que tengan correo de destino."""
    if not smtp_configurado():
        return {"enviadas": 0, "errores": 0, "motivo": "El envío de correo no está configurado"}
    enviadas = errores = 0
    motivo = ""
    try:
        with _conexion() as (smtp, cfg):
            for n in listar("Pendiente"):
                if not n["correo"]:
                    continue
                try:
                    smtp.send_message(_mensaje(cfg, [n["correo"]], n["asunto"], n["mensaje"], None))
                    marcar_enviada(n["id"])
                    enviadas += 1
                except smtplib.SMTPRecipientsRefused:
                    db.update("notificaciones", n["id"], {"estado": "Error"})
                    errores += 1
    except CorreoError as e:
        motivo = str(e)
    return {"enviadas": enviadas, "errores": errores, "motivo": motivo}


def registrar_envio_directo(categoria: str, destinatarios: list[str], asunto: str, mensaje: str,
                            usuario: str = "sistema") -> int:
    """Deja en la bandeja la constancia de un correo que ya se envió."""
    nid = crear(categoria, "Correo", ", ".join(destinatarios), asunto, mensaje,
                correo=", ".join(destinatarios), usuario=usuario)
    marcar_enviada(nid)
    return nid
