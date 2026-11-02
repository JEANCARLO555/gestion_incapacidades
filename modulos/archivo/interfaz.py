"""Pantallas del módulo de archivo."""
import mimetypes
from pathlib import Path

import streamlit as st

from core import auditoria, consultas, flujo, ui
from modulos.archivo import servicio


def render(sesion) -> None:
    st.header("🗄️ Archivo")
    ui.responsables("archivo")
    st.caption("Procedimiento 5.3, 5.5.1 y paso 16 · Archivo físico, depuración y cierre.")
    t0, t1, t2 = st.tabs(["📁 Documentos escaneados", "Archivo físico", "Pagadas por depurar"])
    with t0:
        _escaneados(sesion)
    with t1:
        _fisico(sesion)
    with t2:
        _depurar(sesion)


def _escaneados(sesion) -> None:
    carpetas = servicio.carpetas_escaneadas()
    if not carpetas:
        st.info("Aún no hay documentos escaneados. Se suben en «Verificación documental» → «Copia digital "
                "(escaneo)» y aparecen aquí.")
        return
    buscar = st.text_input("Buscar por colaborador o entidad", key="arc_buscar").strip().lower()
    if buscar:
        carpetas = [c for c in carpetas if buscar in c["colaborador"].lower() or buscar in c["entidad"].lower()]
    ui.tabla(carpetas, sesion, {"colaborador": "Colaborador", "entidad": "Entidad", "fecha_inicio": "Inicio",
                                "fecha_fin": "Fin", "archivos": "Archivos", "ultima_carga": "Última carga",
                                "carpeta": "Carpeta"}, "No hay carpetas que coincidan con la búsqueda.")
    if not carpetas:
        return
    opciones = {c["incapacidad_id"]: f"Incapacidad de {c['colaborador']} · {c['entidad']} · "
                                     f"{c['fecha_inicio']} → {c['fecha_fin']} · {c['archivos']} archivo(s) · "
                                     f"última carga {c['ultima_carga']}" for c in carpetas}
    inc_id = st.selectbox("Ver los documentos de", list(opciones), format_func=opciones.get, key="arc_doc_sel")
    if st.session_state.get("arc_ult_consulta") != inc_id:      # deja huella una vez por consulta
        auditoria.registrar_consulta(sesion, "documentos escaneados", inc_id)
        st.session_state["arc_ult_consulta"] = inc_id
    carpeta = next(c["carpeta"] for c in carpetas if c["incapacidad_id"] == inc_id)
    st.caption("Carpeta en este computador (puede copiarla):")
    st.code(carpeta, language=None)
    if st.button("📂 Abrir la carpeta en el Explorador", key=f"arc_abrir_{inc_id}"):
        try:
            servicio.abrir_carpeta(inc_id)
        except ValueError as e:
            st.error(str(e))
    for d in servicio.documentos_de_incapacidad(inc_id):
        c1, c2, c3, c4 = st.columns([4, 3, 2, 2])
        c1.write(f"**{d['tipo_documento']}**  \n{d['nombre_archivo']}" + ("  \n🩺 clínico: se destruye al archivar" if d["es_clinico"] else ""))
        c2.write(d["subido_en"])
        if not d["existe"]:
            c3.write("❌ No se encuentra")
            continue
        c3.write(f"{d['tamano_kb']} KB")
        datos = servicio.leer_archivo(d["id"])
        c4.download_button("⬇️ Descargar", datos, file_name=d["nombre_archivo"], key=f"arc_dl_{d['id']}",
                           mime=mimetypes.guess_type(d["nombre_archivo"])[0] or "application/octet-stream")
        if Path(d["nombre_archivo"]).suffix.lower() in (".png", ".jpg", ".jpeg"):
            with st.expander(f"Vista previa de {d['nombre_archivo']}"):
                try:
                    st.image(datos)
                except Exception:       # imagen dañada o con un formato raro: no debe tumbar la pantalla
                    st.warning("No se pudo mostrar la vista previa; use «Descargar».")


def _fisico(sesion) -> None:
    ui.tabla(servicio.listado_fisico(), sesion,
             {"entidad": "Entidad", "fecha_inicio": "Inicio", "colaborador": "Colaborador",
              "ubicacion": "Carpeta", "soporte_liquidacion": "Soporte de liquidación", "estado": "Estado"},
             "Aún no hay incapacidades en el archivo físico (orden: entidad y fecha de inicio).")
    filas = consultas.listar_incapacidades()
    if not filas:
        return
    inc_id = ui.selector_incapacidad(filas, "arc_sel")
    c1, c2 = st.columns(2)
    ubic = c1.text_input("Carpeta / ubicación", key="arc_ubic")
    try:
        if c1.button("Guardar ubicación", key="arc_ubic_btn"):
            servicio.asignar_ubicacion(inc_id, ubic, sesion.usuario)
            ui.flash("success", "Ubicación guardada.")
            st.rerun()
        if c2.button("La entidad envió el soporte de liquidación", key="arc_sop"):
            servicio.registrar_soporte_liquidacion(inc_id, sesion.usuario)
            ui.flash("success", "Soporte anexado: queda pendiente para el pago.")
            st.rerun()
    except ValueError as e:
        st.error(str(e))


def _depurar(sesion) -> None:
    filas = servicio.pagadas_por_depurar()
    if not filas:
        st.success("No hay incapacidades pagadas por depurar.")
        return
    ui.tabla(filas, sesion, {"id": "N.º", "colaborador": "Colaborador", "entidad": "Entidad",
                             "verificada": "Verificada", "enviada_gd": "En Gestión Documental",
                             "clinicos_destruidos": "Clínicos destruidos"})
    inc_id = ui.selector_incapacidad(filas, "arc_dep_sel")
    pasos = [("1. Verificar contra el archivo físico", servicio.verificar_contra_pago),
             ("2. Enviar a Gestión Documental", servicio.enviar_a_gestion_documental),
             ("3. Destruir historia clínica / epicrisis", servicio.destruir_clinicos),
             ("4. Cerrar y archivar", servicio.cerrar)]
    for texto, funcion in pasos:
        if st.button(texto, key=f"arc_{texto}"):
            try:
                funcion(inc_id, sesion.usuario)
                ui.flash("success", f"Listo: {texto[3:].lower()}.")
                st.rerun()
            except (ValueError, flujo.FlujoError) as e:
                st.error(str(e))
    st.caption("Recuerde destruir también los documentos clínicos físicos: la aplicación solo borra las copias digitales.")
