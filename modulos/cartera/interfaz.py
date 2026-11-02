"""Pantallas del módulo de cartera."""
from datetime import date, timedelta

import streamlit as st

from config import estados
from core import flujo, seguridad, ui
from modulos.cartera import servicio


def render(sesion) -> None:
    st.header("📬 Cartera")
    ui.responsables("cartera")
    st.caption("Procedimiento 5.4.1 y paso 15 · Cobro persuasivo y cobro de cartera.")
    filas = servicio.candidatas()
    if not filas:
        st.success("No hay incapacidades cobradas pendientes de pago.")
        return
    for f in filas:
        f["alerta"] = ("⚠️ Prescripción · " if f["riesgo_prescripcion"] else "") + ("En mora" if f["en_mora"] else "")
    ui.tabla(ui.con_moneda(filas, "pendiente"), sesion, {"id": "N.º", "colaborador": "Colaborador", "entidad": "Entidad",
                             "estado": "Estado", "fecha_promesa_pago": "Promesa de pago",
                             "dias_desde_cobro": "Días de cobro", "requerimientos": "Requerimientos",
                             "pendiente": "Pendiente EPS", "vence_3_anios": "Límite 3 años",
                             "alerta": "Alerta"})
    inc_id = ui.selector_incapacidad(filas, "car_sel")
    inc = next(f for f in filas if f["id"] == inc_id)
    puede_gestionar = sesion.rol in seguridad.ROLES_COBRO_PERSUASIVO
    try:
        if inc["estado"] == estados.COBRADA and puede_gestionar:
            _persuasivo(sesion, inc_id)
        elif inc["estado"] == estados.EN_CARTERA:
            _cartera(sesion, inc_id)
    except (ValueError, flujo.FlujoError) as e:
        st.error(str(e))
    ui.tabla(servicio.bitacora(inc_id), sesion, {"fecha": "Fecha", "etapa": "Etapa", "tipo": "Tipo",
                                                 "detalle": "Detalle", "usuario": "Usuario"},
             "Sin gestiones registradas.")


def _persuasivo(sesion, inc_id: int) -> None:
    st.subheader("Cobro persuasivo")
    if st.button("Generar requerimiento de cobro", key="car_gen"):
        st.session_state["car_texto"] = servicio.generar_requerimiento(inc_id, sesion.usuario)
        st.rerun()
    if st.session_state.get("car_texto"):
        st.text_area("Texto del requerimiento (cópielo y complételo)", st.session_state["car_texto"],
                     height=260, key="car_texto_area")
    c1, c2 = st.columns(2)
    nueva = c1.date_input("Nueva fecha de pago acordada", value=date.today() + timedelta(days=30), key="car_acu")
    detalle = c2.text_input("Detalle del acuerdo", key="car_acu_det")
    if c1.button("Registrar acuerdo de pago", key="car_acu_btn"):
        servicio.registrar_acuerdo_pago(inc_id, nueva, detalle, sesion.usuario)
        ui.flash("success", "Acuerdo registrado.")
        st.rerun()
    evidencia = c2.text_input("Evidencia de deterioro crediticio de la entidad", key="car_det")
    if c2.button("Registrar deterioro crediticio", key="car_det_btn"):
        servicio.marcar_deterioro_crediticio(inc_id, evidencia, sesion.usuario)
        ui.flash("success", "Evidencia registrada.")
        st.rerun()
    st.subheader("Trasladar a cartera")
    forzar = False
    if sesion.rol == seguridad.ROL_COORDINACION:
        forzar = st.checkbox("Saltar condiciones (requiere justificación)", key="car_forzar")
    just = st.text_input("Justificación", key="car_just") if forzar else ""
    if st.button("Trasladar a cartera", key="car_tras"):
        servicio.trasladar_a_cartera(inc_id, sesion.usuario, forzar=forzar, justificacion=just)
        ui.flash("success", "Trasladada a cartera.")
        st.rerun()


def _cartera(sesion, inc_id: int) -> None:
    st.subheader("Gestión de cartera")
    detalle = st.text_area("Gestión realizada", key="car_gc")
    if st.button("Registrar gestión de cartera", key="car_gc_btn"):
        servicio.registrar_gestion_cartera(inc_id, detalle, sesion.usuario)
        ui.flash("success", "Gestión registrada.")
        st.rerun()
    if st.button("Gestiones agotadas: pasar a Jurídica", key="car_jur"):
        servicio.escalar_a_juridico(inc_id, sesion.usuario)
        ui.flash("success", "Enviada al área jurídica.")
        st.rerun()
