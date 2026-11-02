"""Pantallas del módulo jurídico."""
from datetime import date

import streamlit as st

from config import estados
from core import flujo, ui
from modulos.juridico import servicio


def render(sesion) -> None:
    st.header("⚖️ Cobro jurídico")
    ui.responsables("juridico")
    st.caption("Procedimiento 5.4.2 · Derecho de petición → tutela → recuperar o dar de baja.")
    filas = servicio.elegibles()
    if not filas:
        st.success("No hay casos para cobro jurídico.")
        return
    ui.tabla(filas, sesion, {"id": "N.º", "colaborador": "Colaborador", "entidad": "Entidad",
                             "tipo": "Tipo", "estado": "Estado", "motivo": "Motivo"})
    inc_id = ui.selector_incapacidad(filas, "jur_sel")
    inc = next(f for f in filas if f["id"] == inc_id)
    try:
        if inc["estado"] != estados.EN_JURIDICO:
            if st.button("Abrir cobro jurídico", type="primary", key="jur_abrir"):
                servicio.abrir_caso(inc_id, sesion.usuario)
                ui.flash("success", "Caso abierto en jurídico.")
                st.rerun()
        else:
            _gestionar(sesion, inc_id)
    except (ValueError, flujo.FlujoError) as e:
        st.error(str(e))
    ui.tabla(servicio.bitacora(inc_id), sesion, {"fecha": "Fecha", "tipo": "Tipo", "detalle": "Detalle",
                                                 "radicado": "Radicado", "respondida": "Respondida"},
             "Sin gestiones jurídicas.")


def _gestionar(sesion, inc_id: int) -> None:
    est = servicio.estado_peticion(inc_id)
    if est["hay_pendiente"]:
        st.info(f"Derecho de petición sin respuesta: {est['dias_habiles']} días hábiles "
                f"(término supuesto: {servicio.DIAS_HABILES_RESPUESTA}).")
    c1, c2 = st.columns(2)
    fecha = c1.date_input("Fecha de radicación", value=date.today(), key="jur_fecha")
    radicado = c2.text_input("N.º de radicado", key="jur_rad")
    if c1.button("Radicar derecho de petición", key="jur_dp"):
        st.session_state["jur_texto"] = servicio.radicar_derecho_peticion(inc_id, fecha, radicado, sesion.usuario)
        st.rerun()
    if st.session_state.get("jur_texto"):
        st.text_area("Texto del derecho de petición (complete los fundamentos)",
                     st.session_state["jur_texto"], height=260, key="jur_texto_area")
    if c2.button("Radicar acción de tutela", key="jur_tutela"):
        servicio.radicar_tutela(inc_id, fecha, radicado, sesion.usuario)
        ui.flash("success", "Tutela registrada.")
        st.rerun()
    sin_respuesta = servicio._peticiones_sin_respuesta(inc_id)
    if sin_respuesta and st.button("Marcar la última petición como respondida", key="jur_resp"):
        servicio.registrar_respuesta(sin_respuesta[-1]["id"], sesion.usuario)
        st.rerun()
    st.subheader("Decisión final")
    decision = st.radio("Decisión", ["Recuperar", "Dar de baja"], horizontal=True, key="jur_dec")
    just = st.text_input("Justificación", key="jur_just")
    if st.button("Registrar decisión", key="jur_dec_btn"):
        servicio.decidir(inc_id, decision, just, sesion.usuario)
        ui.flash("success", "Decisión registrada.")
        st.rerun()
