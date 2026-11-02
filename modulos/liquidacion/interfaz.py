"""Pantallas del módulo de liquidación."""
import pandas as pd
import streamlit as st

from config import reglas_pago
from core import ui
from core.utils import moneda
from modulos.liquidacion import servicio


def render(sesion) -> None:
    st.header("🧮 Liquidación de incapacidades")
    ui.responsables("liquidacion")
    st.caption("Procedimiento 5.5.2 · Quién paga cada día y cuánto.")
    tab_inc, tab_calc, tab_reglas = st.tabs(["Por incapacidad", "Calculadora", "Reglas"])
    with tab_inc:
        _por_incapacidad(sesion)
    with tab_calc:
        _calculadora()
    with tab_reglas:
        _reglas()


def _por_incapacidad(sesion) -> None:
    filas = servicio.listar()
    if not filas:
        st.info("Aún no hay incapacidades registradas.")
        return
    inc_id = ui.selector_incapacidad(filas, "liq_sel")
    elegida = next(f for f in filas if f["id"] == inc_id)
    if not elegida["ibc"]:
        st.warning("El colaborador no tiene IBC registrado, por eso todo sale en $0. "
                   "Corríjalo en Recepción → Colaboradores → «Editar un colaborador».")
    r = servicio.liquidar(inc_id)
    if not r["aplica"]:
        st.warning(r["motivo"])
        return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total a pagar al trabajador (días 1 a 180)", moneda(r["total_trabajador"]),
              help="Es lo que se le paga por nómina por esta incapacidad: lo que asume la empresa más lo que reconoce la EPS.")
    c2.metric("Lo asume la empresa", moneda(r["valor_empresa"]), help="Los 2 primeros días al 100 %. No se cobra a nadie.")
    c3.metric("Lo debe reconocer la EPS", moneda(r["valor_eps"]),
              help="Es lo que luego se cobra a la entidad. Cuando la EPS lo consigna, se registra en Conciliación.")
    c4.metric("Días sin pago por nómina (181+)", r["dias_tramite_colaborador"],
              help="Desde el día 181 el pago lo gestiona el colaborador ante el fondo de pensiones o la EPS.")
    st.info("En **Conciliación** NO se le paga al trabajador: allí se registra el dinero que la EPS le consigna a la "
            "empresa (el valor «Lo debe reconocer la EPS»). El pago al trabajador sale por nómina "
            "(módulo Novedades de nómina).")
    st.caption(f"Días acumulados previos (prórrogas): {r['dias_previos']} · "
               f"Valor diario del IBC: {moneda(r['valor_dia'])}")
    st.dataframe(pd.DataFrame([{"Responsable": t["responsable"],
                                "Porcentaje": "—" if t["porcentaje"] is None else f"{t['porcentaje']:.0%}",
                                "Días": t["dias"], "Valor": moneda(t["valor"])}
                               for t in r["tramos"]]), hide_index=True)
    with st.expander("Ver detalle día por día"):
        st.dataframe(pd.DataFrame(servicio.detalle_diario(inc_id)), hide_index=True)


def _calculadora() -> None:
    st.caption("Sirve para simular una incapacidad SIN guardar nada: escriba un IBC, los días que ya lleva acumulados "
               "(si es una prórroga) y los días de esta incapacidad, y verá día por día quién paga y cuánto. "
               "Es útil para comprobar un caso antes de registrarlo o para explicar los porcentajes. "
               "El IBC de 2.000.000 es solo un ejemplo: cámbielo.")
    c1, c2, c3 = st.columns(3)
    ibc = c1.number_input("IBC mensual (ejemplo)", min_value=0.0, step=100000.0, value=2_000_000.0,
                          format="%.0f", key="liq_ibc")
    previos = c2.number_input("Días acumulados previos", min_value=0, value=0, key="liq_prev",
                              help="Días de incapacidades anteriores de las que esta es prórroga.")
    dias = c3.number_input("Días de esta incapacidad", min_value=1, value=10, key="liq_dias")
    try:
        filas = servicio.simular(ibc, int(previos), int(dias))
    except ValueError as e:
        st.error(str(e))
        return
    st.dataframe(pd.DataFrame([{"Día acumulado": f["dia_acumulado"], "Responsable": f["responsable"],
                                "Porcentaje": "—" if f["porcentaje"] is None else f"{f['porcentaje']:.0%}",
                                "Valor": moneda(f["valor"])} for f in filas]), hide_index=True)
    empresa = sum(f["valor"] for f in filas if f["responsable"] == reglas_pago.EMPRESA)
    eps = sum(f["valor"] for f in filas if f["responsable"] == reglas_pago.EPS)
    m1, m2, m3 = st.columns(3)
    m1.metric("Lo asume la empresa", moneda(empresa))
    m2.metric("Lo reconoce la EPS", moneda(eps))
    m3.metric("Total al trabajador", moneda(empresa + eps))


def _reglas() -> None:
    st.dataframe(pd.DataFrame([{"Desde el día": t.desde, "Hasta el día": t.hasta or "en adelante",
                                "Porcentaje del IBC": "—" if t.porcentaje is None else f"{t.porcentaje:.0%}",
                                "Responsable": t.responsable} for t in reglas_pago.TRAMOS]),
                 hide_index=True)
    st.caption("Se aplican a: " + ", ".join(sorted(reglas_pago.TIPOS_CON_REGLA)) +
               ". Para accidente laboral y licencias el procedimiento no define el cálculo.")
