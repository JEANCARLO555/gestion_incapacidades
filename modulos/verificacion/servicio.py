"""
Verificación documental (5.1.2 y paso 4).

El auxiliar revisa que la incapacidad y su documentación estén completas, avisa
al colaborador de lo que falta (3 días hábiles) y, si no responde, hace un
segundo llamado. Cuando todo está completo, la incapacidad queda «Verificada».
También se guarda la copia digital organizada por entidad, colaborador y fecha.
"""
from datetime import date

from config import estados, reglas_documentos as rd, settings
from core import archivos, auditoria, consultas, flujo, notificaciones
from core.utils import a_fecha, ahora_iso, nombre_seguro, sumar_dias_habiles
from modulos.verificacion import repositorio as repo


def pendientes() -> list[dict]:
    return consultas.listar_incapacidades(estados=[estados.RECIBIDA, estados.INCOMPLETA],
                                          orden="i.fecha_recepcion, i.id")


def faltantes(inc_id: int) -> list[str]:
    inc = consultas.obtener_incapacidad(inc_id)
    falta = [d["documento"] for d in consultas.documentos_de(inc_id) if not d["recibido"]]
    if not inc["llegada_fisica"]:
        falta.append("Documentación física en Administración de personal")
    return falta


def estado_llamados(inc_id: int, hoy: date | None = None) -> dict:
    hoy = hoy or date.today()
    llamados = repo.llamados_de(inc_id)
    primero = llamados[0] if llamados else None
    limite = a_fecha(primero["fecha_limite"]) if primero else None
    vencido = bool(limite and hoy > limite)
    return {"cantidad": len(llamados), "fecha_limite": limite, "vencido": vencido,
            "requiere_segundo_llamado": len(llamados) == 1 and vencido}


def _aviso(inc: dict, faltan: list[str], numero: int, limite: date, adicional: str, usuario: str):
    cuerpo = notificaciones.render_plantilla(
        "aviso_documentacion_faltante", nombre=inc["colaborador"], tipo=inc["tipo"].lower(),
        fecha_inicio=inc["fecha_inicio"], fecha_fin=inc["fecha_fin"], entidad=inc["entidad"],
        faltantes="\n".join(f"- {f}" for f in faltan), fecha_limite=limite.isoformat(),
        numero_llamado="primer aviso" if numero == 1 else "segundo llamado",
        aviso_adicional=adicional)
    notificaciones.crear("Documentación", "Colaborador", inc["colaborador"],
                         f"Documentación pendiente de su incapacidad (llamado {numero})", cuerpo,
                         inc["id"], correo=inc["correo"] or None, usuario=usuario)


def verificar(inc_id: int, documentos_recibidos, llegada_fisica: bool, usuario="sistema",
              hoy: date | None = None) -> dict:
    """Actualiza lo recibido; si está completo pasa a «Verificada», si no, avisa al colaborador."""
    hoy = hoy or date.today()
    inc = consultas.obtener_incapacidad(inc_id)
    if not inc or inc["estado"] not in (estados.RECIBIDA, estados.INCOMPLETA):
        raise flujo.FlujoError("Solo se verifican incapacidades recibidas o con documentación incompleta.")
    repo.actualizar_documentos(inc_id, set(documentos_recibidos))
    repo.actualizar_llegada_fisica(inc_id, llegada_fisica)
    faltan = faltantes(inc_id)

    if not faltan:
        flujo.cambiar_estado(inc_id, estados.VERIFICADA, usuario, "Documentación completa")
        return {"completa": True, "faltantes": [], "llamado": None}

    if inc["estado"] == estados.RECIBIDA:
        flujo.cambiar_estado(inc_id, estados.INCOMPLETA, usuario, "; ".join(faltan))
    if repo.llamados_de(inc_id):
        return {"completa": False, "faltantes": faltan, "llamado": None}
    limite = sumar_dias_habiles(hoy, rd.DIAS_HABILES_PARA_COMPLETAR_DOCUMENTACION)
    repo.insertar_llamado({"incapacidad_id": inc_id, "numero": 1, "fecha": hoy.isoformat(),
                           "fecha_limite": limite.isoformat(), "faltantes": "; ".join(faltan),
                           "usuario": usuario})
    _aviso(inc, faltan, 1, limite, "", usuario)
    return {"completa": False, "faltantes": faltan, "llamado": 1, "fecha_limite": limite}


def registrar_segundo_llamado(inc_id: int, usuario="sistema", hoy: date | None = None) -> None:
    hoy = hoy or date.today()
    inc = consultas.obtener_incapacidad(inc_id)
    if not inc or inc["estado"] != estados.INCOMPLETA:
        raise flujo.FlujoError("La incapacidad no está pendiente de documentación.")
    info = estado_llamados(inc_id, hoy)
    if info["cantidad"] == 0:
        raise flujo.FlujoError("Primero debe hacerse el primer aviso.")
    if info["cantidad"] >= 2:
        raise flujo.FlujoError("El segundo llamado ya fue registrado.")
    if not info["vencido"]:
        raise flujo.FlujoError(f"El colaborador tiene plazo hasta el {info['fecha_limite']}.")
    faltan = faltantes(inc_id)
    repo.insertar_llamado({"incapacidad_id": inc_id, "numero": 2, "fecha": hoy.isoformat(),
                           "fecha_limite": None, "faltantes": "; ".join(faltan), "usuario": usuario})
    _aviso(inc, faltan, 2, info["fecha_limite"],
           "De no hacer llegar la documentación será citado con la coordinación de "
           "Administración de personal.", usuario)
    auditoria.registrar(usuario, "segundo llamado", "incapacidad", inc_id, "; ".join(faltan))


def guardar_archivo_digital(inc_id: int, tipo_documento: str, nombre_archivo: str,
                            contenido: bytes, usuario="sistema") -> str:
    """Guarda la copia escaneada en archivos_digitales/<entidad>/<colaborador>_<fecha inicio>/."""
    inc = consultas.obtener_incapacidad(inc_id)
    if not inc:
        raise ValueError("Incapacidad no encontrada.")
    if not contenido:
        raise ValueError("El archivo está vacío.")
    carpeta = (settings.ARCHIVOS_DIR / nombre_seguro(inc["entidad"]) /
               f"{nombre_seguro(inc['colaborador'])}_{inc['fecha_inicio']}")
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"{nombre_seguro(tipo_documento)[:40]}_{nombre_seguro(nombre_archivo)}"
    n = 1
    while destino.exists():
        destino = destino.with_name(f"{destino.stem}_{n}{destino.suffix}")
        n += 1
    destino.write_bytes(contenido)
    repo.insertar_archivo({"incapacidad_id": inc_id, "tipo_documento": tipo_documento,
                           "nombre_archivo": nombre_archivo, "ruta": archivos.a_relativa(destino),
                           "es_clinico": int(tipo_documento in rd.DOCUMENTOS_CLINICOS),
                           "usuario": usuario})
    auditoria.registrar(usuario, "archivo digital", "incapacidad", inc_id, tipo_documento)
    return str(destino)


def archivos_de(inc_id: int) -> list[dict]:
    return repo.archivos_de(inc_id)
