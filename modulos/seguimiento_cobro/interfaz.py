"""Pantallas del módulo de seguimiento de cobro."""
from datetime import date, timedelta

import streamlit as st

from config import estados
from core import flujo, ui
from modulos.seguimiento_cobro import servicio


def render(sesion) -> None:
    st.header("💰 Seguimiento de cobro")
    ui.responsables("seguimiento_cobro")
    st.caption("Procedimiento 5.4 · Transcrita → Cobrada / Rechazada → Pagada.")
    t1, t2, t3 = st.tabs(["Panel diario", "Cambiar estado", "Seguimiento semanal"])
    with t1:
        _panel(sesion)
    with t2:
        _estados(sesion)
    with t3:
        _semanal(sesion)


def _panel(sesion) -> None:
    conteo = servicio.panel()
    if conteo:
        cols = st.columns(min(len(conteo), 6))
        for col, fila in zip(cols, conteo[:6]):
            col.metric(fila["estado"], fila["cantidad"])
    ui.tabla(servicio.en_gestion(), sesion,
             {"id": "N.º", "colaborador": "Colaborador", "entidad": "Entidad", "tipo": "Tipo",
              "fecha_inicio": "Inicio", "fecha_fin": "Fin", "estado": "Estado",
              "fecha_promesa_pago": "Promesa de pago"}, "Nada en gestión de cobro.")


def _estados(sesion) -> None:
    filas = servicio.en_gestion()
    if not filas:
        st.info("Nada en gestión de cobro.")
        return
    inc_id = ui.selector_incapacidad(filas, "seg_sel")
    inc = next(f for f in filas if f["id"] == inc_id)
    estado = inc["estado"]
    st.write(f"Estado actual: **{estado}**")
    try:
        if estado == estados.TRANSCRITA:
            promesa = st.date_input("Fecha prometida de pago", value=date.today() + timedelta(days=30),
                                    key="seg_promesa")
            if st.button("Marcar como COBRADA (entidad la aceptó)", key="seg_cobrada"):
                servicio.marcar_cobrada(inc_id, promesa, sesion.usuario)
                ui.flash("success", "Marcada como cobrada.")
                st.rerun()
            causal = st.text_input("Causal del rechazo", key="seg_causal")
            improcedente = st.checkbox("La causal es improcedente (va a cobro jurídico)", key="seg_improc")
            if st.button("Marcar como RECHAZADA", key="seg_rechazada"):
                servicio.marcar_rechazada(inc_id, causal, improcedente, sesion.usuario)
                ui.flash("warning", "Marcada como rechazada.")
                st.rerun()
        elif estado == estados.RECHAZADA:
            if st.button("Causal subsanada: permitir nueva transcripción", key="seg_subsanar"):
                servicio.subsanar_rechazo(inc_id, sesion.usuario)
                ui.flash("success", "Rechazo subsanado: ya aparece en Transcripción.")
                st.rerun()
        if estado in (estados.COBRADA, estados.EN_CARTERA, estados.EN_JURIDICO):
            if st.button("Marcar como PAGADA (la entidad pagó)", key="seg_pagada"):
                servicio.marcar_pagada(inc_id, sesion.usuario)
                ui.flash("success", "Marcada como pagada. Registre el pago en Conciliación.")
                st.rerun()
    except (ValueError, flujo.FlujoError) as e:
        st.error(str(e))


def _semanal(sesion) -> None:
    pend = servicio.pendientes_seguimiento()
    st.subheader("Sin seguimiento en los últimos 7 días")
    ui.tabla(pend, sesion, {"id": "N.º", "colaborador": "Colaborador", "entidad": "Entidad",
                            "estado": "Estado", "ultimo_seguimiento": "Último seguimiento"},
             "Todo al día.")
    filas = servicio.en_gestion()
    if not filas:
        return
    inc_id = ui.selector_incapacidad(filas, "seg_sem_sel")
    detalle = st.text_area("Gestión realizada (evidencia)", key="seg_det")
    if st.button("Registrar seguimiento", key="seg_reg"):
        try:
            servicio.registrar_seguimiento(inc_id, detalle, sesion.usuario)
            ui.flash("success", "Seguimiento registrado.")
            st.rerun()
        except ValueError as e:
            st.error(str(e))
    ui.tabla(servicio.bitacora(inc_id), sesion, {"fecha": "Fecha", "etapa": "Etapa", "tipo": "Tipo",
                                                 "detalle": "Detalle", "usuario": "Usuario"},
             "Sin gestiones registradas.")
