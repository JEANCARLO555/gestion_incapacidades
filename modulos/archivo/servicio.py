"""
Archivo físico y cierre (5.3, 5.5.1 y paso 16).

  - El archivo físico se organiza por entidad y fecha de inicio, de forma ascendente.
  - Cuando llega el soporte de liquidación de la entidad se anexa a la incapacidad.
  - Pagada la incapacidad: se verifica contra el archivo físico (5.5.1), se envía a
    Gestión Documental y se DESTRUYEN la historia clínica y la epicrisis (paso 16).
  - Con los tres pasos hechos, la incapacidad queda «Archivada».
"""
import os
import sys
from datetime import date
from pathlib import Path

from config import estados
from core import archivos, auditoria, consultas, flujo
from core.utils import ahora_iso
from modulos.archivo import repositorio as repo


def asignar_ubicacion(inc_id: int, ubicacion: str, usuario="sistema") -> None:
    if not ubicacion.strip():
        raise ValueError("Indique la carpeta o ubicación del archivo físico.")
    if not consultas.obtener_incapacidad(inc_id):
        raise ValueError("Incapacidad no encontrada.")
    repo.guardar(inc_id, {"ubicacion": ubicacion.strip(), "fecha_archivo": date.today().isoformat(),
                          "usuario": usuario})
    auditoria.registrar(usuario, "archivo físico", "incapacidad", inc_id, ubicacion.strip())


def registrar_soporte_liquidacion(inc_id: int, usuario="sistema") -> None:
    if not repo.obtener(inc_id):
        raise ValueError("Primero asigne la ubicación del archivo físico.")
    repo.guardar(inc_id, {"soporte_liquidacion": 1, "fecha_soporte": date.today().isoformat(),
                          "usuario": usuario})


def listado_fisico() -> list[dict]:
    """Ordenado por entidad y fecha de inicio ascendente (5.3)."""
    return repo.listado_fisico()


def pagadas_por_depurar() -> list[dict]:
    filas = []
    for inc in consultas.listar_incapacidades(estados=[estados.PAGADA], orden="i.entidad, i.fecha_inicio"):
        a = repo.obtener(inc["id"]) or {}
        filas.append({**inc, "ubicacion": a.get("ubicacion"),
                      "verificada": bool(a.get("verificada_pago")),
                      "enviada_gd": bool(a.get("fecha_envio_gd")),
                      "clinicos_destruidos": bool(a.get("clinicos_destruidos"))})
    return filas


def _pagada(inc_id: int) -> dict:
    inc = consultas.obtener_incapacidad(inc_id)
    if not inc or inc["estado"] != estados.PAGADA:
        raise flujo.FlujoError("La incapacidad debe estar «Pagada».")
    return inc


def verificar_contra_pago(inc_id: int, usuario="sistema") -> None:
    """5.5.1: se verifica la incapacidad pagada contra la física para depurar el archivo."""
    _pagada(inc_id)
    repo.guardar(inc_id, {"verificada_pago": date.today().isoformat(), "usuario": usuario})
    auditoria.registrar(usuario, "verificar contra pago", "incapacidad", inc_id)


def enviar_a_gestion_documental(inc_id: int, usuario="sistema") -> None:
    _pagada(inc_id)
    a = repo.obtener(inc_id)
    if not a or not a.get("verificada_pago"):
        raise flujo.FlujoError("Primero debe verificarse la incapacidad pagada contra el archivo físico.")
    repo.guardar(inc_id, {"fecha_envio_gd": date.today().isoformat(), "usuario": usuario})
    auditoria.registrar(usuario, "envío a gestión documental", "incapacidad", inc_id)


def destruir_clinicos(inc_id: int, usuario="sistema") -> int:
    """Paso 16: la historia clínica y la epicrisis no reposan en el archivo. Borra las copias digitales."""
    _pagada(inc_id)
    borrados = 0
    for archivo in repo.archivos_clinicos_vigentes(inc_id):
        ruta = archivos.a_absoluta(archivo["ruta"])
        if not archivos.esta_dentro(ruta):
            raise ValueError("Un archivo tiene una ruta fuera de la carpeta de archivos digitales; "
                             "no se borra nada. Revise con el administrador.")
        try:
            os.remove(ruta)
        except FileNotFoundError:
            pass
        repo.marcar_eliminado(archivo["id"], ahora_iso())
        borrados += 1
    repo.guardar(inc_id, {"clinicos_destruidos": date.today().isoformat(), "usuario": usuario})
    auditoria.registrar(usuario, "destrucción de documentos clínicos", "incapacidad", inc_id,
                        f"{borrados} archivo(s) digital(es); recuerde destruir también los físicos")
    return borrados


def cerrar(inc_id: int, usuario="sistema") -> None:
    _pagada(inc_id)
    a = repo.obtener(inc_id) or {}
    faltan = [txt for campo, txt in (("verificada_pago", "verificación contra el pago"),
                                     ("fecha_envio_gd", "envío a Gestión Documental"),
                                     ("clinicos_destruidos", "destrucción de documentos clínicos"))
              if not a.get(campo)]
    if faltan:
        raise flujo.FlujoError("Falta: " + ", ".join(faltan) + ".")
    flujo.cambiar_estado(inc_id, estados.ARCHIVADA, usuario, "Archivo cerrado")


# ---------------------------------------------------------------- documentos escaneados
def carpetas_escaneadas() -> list[dict]:
    """Una fila por incapacidad que tiene copias digitales: carpeta, cuántos archivos y última carga."""
    filas = []
    for f in repo.carpetas_con_archivos():
        carpeta = archivos.a_absoluta(f["ruta_ejemplo"]).parent
        filas.append({**f, "carpeta": str(carpeta)})
    return filas


def documentos_de_incapacidad(inc_id: int) -> list[dict]:
    docs = []
    for a in repo.archivos_vigentes(inc_id):
        ruta = archivos.a_absoluta(a["ruta"])
        existe = ruta.is_file() and archivos.esta_dentro(ruta)
        docs.append({**a, "ruta_completa": str(ruta), "existe": existe,
                     "tamano_kb": round(ruta.stat().st_size / 1024, 1) if existe else None})
    return docs


def leer_archivo(archivo_id: int) -> bytes:
    a = repo.obtener_archivo(archivo_id)
    if not a:
        raise ValueError("El archivo no existe o fue destruido.")
    ruta = archivos.a_absoluta(a["ruta"])
    if not archivos.esta_dentro(ruta):
        raise ValueError("El archivo está fuera de la carpeta de archivos digitales.")
    if not ruta.is_file():
        raise ValueError("No se encuentra el archivo en la carpeta (¿lo movieron o lo borraron?).")
    return ruta.read_bytes()


def abrir_carpeta(inc_id: int) -> str:
    """Abre la carpeta en el Explorador de Windows (en el computador donde corre la aplicación)."""
    docs = documentos_de_incapacidad(inc_id)
    if not docs:
        raise ValueError("Esta incapacidad no tiene documentos escaneados.")
    carpeta = Path(docs[0]["ruta_completa"]).parent
    if sys.platform != "win32":
        raise ValueError("Abrir la carpeta solo funciona en Windows. Copie la ruta y ábrala a mano.")
    if not carpeta.is_dir():
        raise ValueError("La carpeta no existe en este computador.")
    os.startfile(carpeta)  # noqa: S606 (solo Windows; la ruta sale de nuestra propia base de datos)
    return str(carpeta)
