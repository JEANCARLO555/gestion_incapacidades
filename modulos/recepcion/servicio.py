"""
Recepción de incapacidades (5.1.1 y pasos 1 a 3 del desarrollo).

Aquí solo se REGISTRA lo que llegó y por qué canal. La revisión de que todo esté
completo la hace el módulo de verificación.
"""
from datetime import date

from config import estados, reglas_documentos as rd, settings
from core import auditoria, consultas, flujo, notificaciones, seguridad
from core.utils import a_fecha, a_iso, dias_inclusivos, normalizar_texto
from modulos.recepcion import repositorio as repo


def registrar_colaborador(documento, nombre, cargo="", area="", jefe_inmediato="",
                          correo="", ibc=0.0, usuario="sistema") -> int:
    documento, nombre = str(documento).strip(), str(nombre).strip()
    if not documento or not nombre:
        raise ValueError("El documento y el nombre son obligatorios.")
    if ibc < 0:
        raise ValueError("El IBC no puede ser negativo.")
    if repo.buscar_colaborador_por_documento(documento):
        raise ValueError(f"Ya existe un colaborador con el documento {documento}.")
    cid = repo.insertar_colaborador({
        "documento": documento, "nombre": nombre, "cargo": cargo.strip(), "area": area.strip(),
        "jefe_inmediato": jefe_inmediato.strip(), "correo": correo.strip(), "ibc": float(ibc)})
    auditoria.registrar(usuario, "crear", "colaborador", cid, nombre)
    return cid


def actualizar_colaborador(colaborador_id: int, nombre=None, cargo=None, area=None,
                           jefe_inmediato=None, correo=None, ibc=None, usuario="sistema") -> None:
    """Corrige datos de un colaborador (por ejemplo el IBC, que define lo que paga la EPS)."""
    if not consultas.obtener_colaborador(colaborador_id):
        raise ValueError("Colaborador no encontrado.")
    cambios = {k: (v.strip() if isinstance(v, str) else v) for k, v in
               {"nombre": nombre, "cargo": cargo, "area": area, "jefe_inmediato": jefe_inmediato,
                "correo": correo, "ibc": ibc}.items() if v is not None}
    if "nombre" in cambios and not cambios["nombre"]:
        raise ValueError("El nombre no puede quedar vacío.")
    if cambios.get("ibc") is not None and cambios["ibc"] < 0:
        raise ValueError("El IBC no puede ser negativo.")
    if not cambios:
        return
    repo.actualizar_colaborador(colaborador_id, cambios)
    auditoria.registrar(usuario, "editar colaborador", "colaborador", colaborador_id, ", ".join(cambios))


def documentos_requeridos(tipo: str, fecha_inicio, fecha_fin) -> list[str]:
    return rd.documentos_requeridos(tipo, dias_inclusivos(fecha_inicio, fecha_fin))


def advertencias(canal: str, llegada_fisica: bool, informo_jefe: bool, fecha_inicio,
                 fecha_recepcion=None) -> list[str]:
    """Avisos (no bloquean el registro) según lo que dice el procedimiento."""
    avisos = []
    if canal == "Correo electrónico" and not llegada_fisica:
        avisos.append("Llegó por correo: el colaborador debe hacer llegar la documentación "
                      "física a Administración de personal (5.1.1).")
    elif not llegada_fisica:
        avisos.append("En todos los casos la documentación debe llegar físicamente a "
                      "Administración de personal (5.1.1).")
    if not informo_jefe:
        avisos.append("El colaborador debe informar de inmediato al jefe inmediato y a "
                      "Administración de personal (5.1.1).")
    recepcion = a_fecha(fecha_recepcion) or date.today()
    demora = (recepcion - a_fecha(fecha_inicio)).days
    if demora > rd.DIAS_MAXIMOS_ENVIO_COLABORADOR:
        avisos.append(f"Se recibió {demora} días después del inicio; el procedimiento pide "
                      f"enviarla máximo {rd.DIAS_MAXIMOS_ENVIO_COLABORADOR} días después de "
                      "conferida (paso 3).")
    return avisos


def registrar_incapacidad(colaborador_id, tipo, entidad, fecha_inicio, fecha_fin, canal,
                          recibido_por, informo_jefe, llegada_fisica, documentos_recibidos,
                          fecha_recepcion=None, observaciones="", prorroga_de=None,
                          fecha_nacimiento=None, usuario="sistema") -> int:
    colaborador = consultas.obtener_colaborador(colaborador_id)
    if not colaborador:
        raise ValueError("Colaborador no encontrado.")
    if tipo not in rd.TIPOS_INCAPACIDAD:
        raise ValueError("Tipo de incapacidad no válido.")
    if canal not in settings.CANALES_RECEPCION:
        raise ValueError("Canal de recepción no válido.")
    if entidad not in settings.ENTIDADES:
        raise ValueError("Entidad no válida.")
    ini, fin = a_fecha(fecha_inicio), a_fecha(fecha_fin)
    if fin < ini:
        raise ValueError("La fecha de fin no puede ser anterior a la de inicio.")
    if prorroga_de:
        anterior = consultas.obtener_incapacidad(prorroga_de)
        if not anterior or anterior["colaborador_id"] != colaborador_id:
            raise ValueError("La incapacidad que se prorroga no existe o es de otra persona.")
        if repo.tiene_prorroga(prorroga_de):
            raise ValueError("Esa incapacidad ya tiene una prórroga registrada.")

    dias = dias_inclusivos(ini, fin)
    marcados = set(documentos_recibidos)
    recibidos = {d: d in marcados for d in rd.documentos_requeridos(tipo, dias)}
    inc_id = repo.insertar_incapacidad({
        "colaborador_id": colaborador_id, "tipo": tipo, "entidad": entidad,
        "fecha_inicio": ini.isoformat(), "fecha_fin": fin.isoformat(), "dias": dias,
        "fecha_nacimiento": a_iso(fecha_nacimiento), "prorroga_de": prorroga_de,
        "canal_recepcion": canal, "recibido_por": recibido_por.strip(),
        "fecha_recepcion": (a_fecha(fecha_recepcion) or date.today()).isoformat(),
        "informo_jefe": int(informo_jefe), "llegada_fisica": int(llegada_fisica),
        "estado": estados.RECIBIDA, "observaciones": observaciones.strip()})
    repo.insertar_documentos(inc_id, recibidos)
    flujo.registrar_estado_inicial(inc_id, estados.RECIBIDA, usuario)
    auditoria.registrar(usuario, "recepción", "incapacidad", inc_id,
                        f"{tipo} {ini} a {fin} por {canal}")

    asunto = f"Incapacidad recibida: {colaborador['nombre']} ({ini} a {fin})"
    cuerpo = (f"Se recibió una {tipo.lower()} de {colaborador['nombre']} del {ini} al {fin} "
              f"({dias} días). Gestionar el reemplazo para garantizar la continuidad de las "
              "actividades.")
    if colaborador["jefe_inmediato"]:
        notificaciones.crear("Recepción", "Jefe inmediato", colaborador["jefe_inmediato"],
                             asunto, cuerpo, inc_id, usuario=usuario)
    notificaciones.crear("Recepción", "Administración de personal", "Administración de personal",
                         asunto, cuerpo, inc_id, correo=settings.CORREO_ADMON_PERSONAL,
                         usuario=usuario)
    return inc_id


def asignar_reemplazo(inc_id: int, reemplazo: str, usuario="sistema") -> None:
    """Paso 2: el líder gestiona el reemplazo del colaborador incapacitado."""
    if not reemplazo.strip():
        raise ValueError("Indique quién reemplaza al colaborador.")
    repo.actualizar_reemplazo(inc_id, reemplazo.strip())
    auditoria.registrar(usuario, "asignar reemplazo", "incapacidad", inc_id, reemplazo.strip())


def listar(sesion: seguridad.Sesion, estados_filtro=None) -> list[dict]:
    """Un líder solo ve las incapacidades de las personas que dependen de él.

    Se compara su usuario con el «Jefe inmediato» sin distinguir mayúsculas, tildes ni espacios."""
    todas = consultas.listar_incapacidades(estados=estados_filtro)
    if sesion.rol != seguridad.ROL_LIDER:
        return todas
    usuario = normalizar_texto(sesion.usuario)
    return [i for i in todas if normalizar_texto(i["jefe_inmediato"]) == usuario]


def cantidad_fuera_del_equipo(sesion: seguridad.Sesion) -> int:
    """Cuántas incapacidades hay que el líder no ve (solo el número, sin datos de nadie)."""
    return len(consultas.listar_incapacidades()) - len(listar(sesion))


def candidatas_a_prorroga(colaborador_id: int) -> list[dict]:
    return [i for i in consultas.listar_incapacidades(colaborador_id=colaborador_id)
            if not repo.tiene_prorroga(i["id"])]
