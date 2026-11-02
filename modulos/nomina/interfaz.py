"""Pantallas del módulo de nómina."""
from datetime import date

import streamlit as st

from core import ui
from modulos.nomina import servicio

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def render(sesion) -> None:
    st.header("🧾 Novedades de nómina")
    ui.responsables("nomina")
    st.caption("Procedimiento 5.2 · Días y valores por mes a cargo de la empresa y de la EPS.")
    hoy = date.today()
    c1, c2 = st.columns(2)
    anio = int(c1.number_input("Año", 2020, 2100, hoy.year, key="nom_anio"))
    mes = int(c2.selectbox("Mes", range(1, 13), index=hoy.month - 1, format_func=lambda m: MESES[m - 1], key="nom_mes"))
    if st.button("Generar novedades del mes", type="primary", key="nom_gen"):
        r = servicio.generar_novedades(anio, mes, sesion.usuario)
        msg = f"Generadas: {r['generadas']}. Ya reportadas (sin cambios): {r['ya_reportadas']}."
        if r["sin_regla"]:
            msg += (f" Sin regla de cálculo en el procedimiento (accidente laboral o licencias): "
                    f"{len(r['sin_regla'])}.")
        ui.flash("info", msg)
        st.rerun()
    filas = servicio.novedades(anio, mes)
    for f in filas:
        f["total_trabajador"] = f["valor_empresa"] + f["valor_eps"]
    filas = ui.con_moneda(filas, "valor_empresa", "valor_eps", "total_trabajador")
    df = ui.tabla(filas, sesion, {"documento": "Documento", "colaborador": "Colaborador", "tipo": "Tipo",
                                  "dias": "Días del mes", "dias_empresa": "Días empresa", "dias_eps": "Días EPS",
                                  "dias_sin_pago_nomina": "Días sin pago (181+)", "valor_empresa": "Lo asume la empresa",
                                  "valor_eps": "Lo reconoce la EPS", "total_trabajador": "Total al trabajador", "reportada": "Reportada"},
                  "Aún no hay novedades para este mes.")
    if filas:
        c3, c4 = st.columns(2)
        if c3.button("Marcar como reportadas a nómina", key="nom_rep"):
            ui.flash("success", f"{servicio.marcar_reportadas(anio, mes, sesion.usuario)} novedades reportadas.")
            st.rerun()
        ui.descargar_csv(df, f"novedades_nomina_{anio}-{mes:02d}.csv", "nom_csv")
