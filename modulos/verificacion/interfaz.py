"""Pantallas del módulo de verificación documental."""
import streamlit as st

from config import reglas_documentos as rd
from core import auditoria, consultas, flujo, seguridad, ui
from modulos.verificacion import servicio


def render(sesion) -> None:
    st.header("🔎 Verificación documental")
    ui.responsables("verificacion")
    st.caption("Procedimiento 5.1.2 · Revisar que todo esté completo, avisar lo que falta y "
               "guardar la copia digital.")
    filas = servicio.pendientes()
    if not filas:
        st.success("No hay incapacidades pendientes de verificación.")
        return
    inc_id = ui.selector_incapacidad(filas, "ver_sel")
    inc = consultas.obtener_incapacidad(inc_id)
    documentos = consultas.documentos_de(inc_id)
    llamados = servicio.estado_llamados(inc_id)

    st.subheader("Lista de chequeo")
    recibidos = [d["documento"] for d in documentos
                 if st.checkbox(d["documento"], value=bool(d["recibido"]),
                                key=f"ver_doc_{inc_id}_{d['id']}")]
    fisica = st.checkbox("Documentación física recibida en Administración de personal",
                         value=bool(inc["llegada_fisica"]), key=f"ver_fis_{inc_id}")

    if llamados["cantidad"]:
        st.info(f"Primer aviso enviado. El colaborador tiene plazo hasta el "
                f"{llamados['fecha_limite']}.")
    if st.button("Verificar y guardar", type="primary", key=f"ver_btn_{inc_id}"):
        try:
            r = servicio.verificar(inc_id, recibidos, fisica, sesion.usuario)
        except flujo.FlujoError as e:
            st.error(str(e))
        else:
            if r["completa"]:
                ui.flash("success", "Documentación completa: la incapacidad quedó «Verificada».")
            else:
                ui.flash("warning", "Documentación incompleta. Falta: " + "; ".join(r["faltantes"]))
            st.rerun()
    if llamados["requiere_segundo_llamado"] and st.button(
            "Registrar segundo llamado", key=f"ver_seg_{inc_id}"):
        try:
            servicio.registrar_segundo_llamado(inc_id, sesion.usuario)
            ui.flash("success", "Segundo llamado registrado.")
            st.rerun()
        except flujo.FlujoError as e:
            st.error(str(e))

    st.subheader("Copia digital (escaneo)")
    st.caption("Se guarda en archivos_digitales/<entidad>/<colaborador>_<fecha de inicio>/")
    tipo_doc = st.selectbox("Documento que se sube",
                            [d["documento"] for d in documentos] + rd.OTROS_DOCUMENTOS,
                            key=f"ver_tipo_{inc_id}")
    archivo = st.file_uploader("Archivo escaneado", key=f"ver_up_{inc_id}")
    if archivo and st.button("Guardar copia digital", key=f"ver_save_{inc_id}"):
        servicio.guardar_archivo_digital(inc_id, tipo_doc, archivo.name, archivo.getvalue(),
                                         sesion.usuario)
        ui.flash("success", "Copia digital guardada.")
        st.rerun()
    if seguridad.puede_ver_datos_clinicos(sesion.rol):
        auditoria.registrar_consulta(sesion, "listado de archivos digitales", inc_id)
        ui.tabla(servicio.archivos_de(inc_id), sesion,
                 {"tipo_documento": "Documento", "nombre_archivo": "Archivo",
                  "subido_en": "Subido"}, "Aún no hay copias digitales.")
