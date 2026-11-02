"""Pantallas del módulo de conciliación."""
from datetime import date

import streamlit as st

from config import settings
from core import ui
from core.utils import moneda
from modulos.conciliacion import servicio

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def render(sesion) -> None:
    st.header("🏦 Conciliación de pagos")
    ui.responsables("conciliacion")
    st.caption("Procedimiento 5.5 · La EPS le paga a la empresa; aquí se registra ese dinero y se "
               "asigna a la incapacidad que corresponde.")
    with st.expander("¿Cómo funciona? (léame primero)"):
        st.markdown(
            "1. **Contabilidad** avisa que una entidad consignó dinero → pestaña **Registrar pago**.\n"
            "2. Se entra al **portal de la entidad** y se baja el *detalle del pago* (qué colaborador, "
            "cuántos días y cuánto valor).\n"
            "3. En **Identificar pagos** se asigna cada línea del detalle a su incapacidad.\n"
            "4. Lo que no se logre identificar se avisa a Contabilidad.\n"
            "5. En **Reporte mensual** queda el detalle por entidad para Contabilidad.\n\n"
            "El valor «esperado» es el «Lo debe reconocer la EPS» de la pantalla **Liquidación**: es solo un "
            "**cálculo de ayuda** (IBC y porcentajes). Lo que manda es el detalle que entrega la entidad.\n\n"
            "**Aquí no se le paga al trabajador.** Aquí entra el dinero que la EPS le paga a la **empresa**. "
            "Lo que se le paga al trabajador sale por nómina (módulo Novedades de nómina).")
    t1, t2, t3, t4 = st.tabs(["Registrar pago", "Identificar pagos", "Saldos por entidad", "Reporte mensual"])
    with t1:
        _registrar(sesion)
    with t2:
        _identificar(sesion)
    with t3:
        _saldos(sesion)
    with t4:
        _reporte(sesion)


def _registrar(sesion) -> None:
    c1, c2 = st.columns(2)
    entidad = c1.selectbox("Entidad que pagó", settings.ENTIDADES, key="con_ent")
    fecha = c2.date_input("Fecha del pago", value=date.today(), key="con_fecha")
    valor = c1.number_input("Valor consignado", min_value=0.0, step=10000.0, key="con_val")
    ref = c2.text_input("Referencia / comprobante", key="con_ref")
    if st.button("Registrar pago", type="primary", key="con_btn"):
        try:
            servicio.registrar_pago(entidad, fecha, valor, ref, sesion.usuario)
            ui.flash("success", "Pago registrado. Ahora asígnelo a una incapacidad en «Identificar pagos».")
            st.rerun()
        except ValueError as e:
            st.error(str(e))
    pagos = servicio.pagos_pendientes()
    if pagos:
        st.caption("Pagos registrados con valor por identificar:")
        ui.tabla(ui.con_moneda(pagos, "valor_total", "sin_identificar"), sesion,
                 {"id": "N.º", "fecha_pago": "Fecha", "entidad": "Entidad",
                                 "valor_total": "Valor", "sin_identificar": "Por identificar",
                                 "referencia": "Referencia"})


def _identificar(sesion) -> None:
    pendientes = servicio.pagos_pendientes()
    if not pendientes:
        st.success("No hay pagos por identificar. Registre uno en la pestaña anterior.")
        return
    opciones = {p["id"]: f"{p['fecha_pago']} · {p['entidad']} · {moneda(p['sin_identificar'])} por identificar"
                for p in pendientes}
    pago_id = st.selectbox("Pago", list(opciones), format_func=opciones.get, key="con_pago")
    pago = next(p for p in pendientes if p["id"] == pago_id)
    sug = servicio.sugerencias(pago_id)
    if not sug:
        st.warning(f"No hay incapacidades de {pago['entidad']} a las que asignar este pago.")
        for mensaje in servicio.diagnostico_entidad(pago["entidad"]):
            st.write("• " + mensaje)
    else:
        st.write("Incapacidades de la misma entidad (las de saldo más parecido al pago, primero):")
        mostrar = [{**f, "coincidencia": "—" if f["coincidencia"] is None else f"{f['coincidencia']:.0%}"}
                   for f in ui.con_moneda(sug, "esperado", "pagado", "saldo")]
        ui.tabla(mostrar, sesion, {"id": "N.º", "colaborador": "Colaborador", "estado": "Estado",
                               "fecha_inicio": "Inicio", "fecha_fin": "Fin", "dias": "Días",
                               "esperado": "Esperado (cálculo)", "pagado": "Ya pagado", "saldo": "Saldo",
                               "coincidencia": "Parecido", "motivo": "Observación"})
        inc_id = ui.selector_incapacidad(sug, "con_inc", "Asignar a la incapacidad")
        elegida = next(f for f in sug if f["id"] == inc_id)
        if elegida["motivo"].startswith("Sin valor calculado"):
            st.info("Esta incapacidad no tiene valor calculado, pero puede asignarle el pago: "
                    "el detalle de la entidad es lo que manda. " + elegida["motivo"])
        c1, c2 = st.columns(2)
        valor = c1.number_input("Valor a asignar", min_value=0.0, value=float(pago["sin_identificar"]),
                                step=10000.0, key=f"con_aplicar_{pago_id}")
        dias = c2.number_input("Días pagados (según el detalle de la entidad; 0 = no indicar)",
                               min_value=0, max_value=int(elegida["dias"]), value=0, key=f"con_dias_{pago_id}_{inc_id}")
        if st.button("Asignar pago a la incapacidad", type="primary", key="con_aplicar_btn"):
            try:
                servicio.aplicar_pago(pago_id, inc_id, valor, sesion.usuario, int(dias) or None)
                ui.flash("success", "Pago asignado.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    if st.button("Avisar a Contabilidad de los pagos sin identificar", key="con_aviso"):
        servicio.notificar_pagos_sin_identificar(sesion.usuario)
        ui.flash("success", "Aviso creado en la bandeja de notificaciones.")
        st.rerun()


def _saldos(sesion) -> None:
    filas = ui.con_moneda(servicio.saldos_por_entidad(), "esperado", "pagado", "saldo")
    ui.tabla(filas, sesion, {"entidad": "Entidad", "incapacidades": "Incapacidades",
                             "sin_valor": "Sin valor calculado", "esperado": "Esperado EPS (cálculo)",
                             "pagado": "Pagado", "saldo": "Saldo que adeuda"},
             "Aún no hay incapacidades transcritas o en cobro.")
    if any(f["sin_valor"] for f in servicio.saldos_por_entidad()):
        st.warning("Hay incapacidades «sin valor calculado», por eso el esperado puede verse en $0. "
                   "Causas frecuentes: el colaborador no tiene IBC (Recepción → Colaboradores), "
                   "la incapacidad dura 2 días o menos, o su tipo no tiene regla de cálculo. "
                   "Se ven una por una en «Identificar pagos».")
    inconsistentes = servicio.pagadas_sin_pago_registrado()
    if inconsistentes:
        st.warning("Incapacidades marcadas «Pagada» sin pago identificado:")
        ui.tabla(inconsistentes, sesion, {"id": "N.º", "colaborador": "Colaborador", "entidad": "Entidad"})


def _reporte(sesion) -> None:
    hoy = date.today()
    c1, c2 = st.columns(2)
    anio = c1.number_input("Año", 2020, 2100, hoy.year, key="con_anio")
    mes = c2.selectbox("Mes", range(1, 13), index=hoy.month - 1, format_func=lambda m: MESES[m - 1], key="con_mes")
    df = servicio.reporte_mensual(int(anio), int(mes))
    if df.empty:
        st.info("No hay pagos identificados en ese mes.")
        return
    st.dataframe(df, hide_index=True)
    ui.descargar_csv(df, f"conciliacion_{int(anio)}-{int(mes):02d}.csv", "con_csv")
