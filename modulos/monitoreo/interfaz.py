"""Pantallas del módulo de monitoreo."""
from datetime import date

import pandas as pd
import streamlit as st

from config import reglas_monitoreo as rm
from core import consultas, ui
from modulos.monitoreo import servicio

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def render(sesion) -> None:
    st.header("📈 Monitoreo de incapacidades prolongadas")
    ui.responsables("monitoreo")
    st.caption("Procedimiento 5.5.3 · Hitos de 90, 120, 150 y 180 días.")
    t1, t2, t3 = st.tabs(["Reporte mensual", "Concepto de rehabilitación", "Reintegros (>180 días)"])
    with t1:
        _reporte(sesion)
    with t2:
        _rehabilitacion(sesion)
    with t3:
        _reintegros(sesion)


def _reporte(sesion) -> None:
    st.caption("Lista los casos (una incapacidad y sus prórrogas) que, al cierre del mes elegido, llevan MÁS de "
               "90, 120, 150 o 180 días acumulados. Es el reporte mensual que pide el 5.5.3. Si una incapacidad "
               "es de 257 días, no aparecerá en el mes de inicio sino cuando pase de 90: puede verlo cambiando el mes.")
    hoy = date.today()
    c1, c2 = st.columns(2)
    anio = c1.number_input("Año", 2020, 2100, hoy.year, key="mon_anio")
    mes = c2.selectbox("Mes", range(1, 13), index=hoy.month - 1, format_func=lambda m: MESES[m - 1],
                       key="mon_mes")
    filas = servicio.reporte_mensual(int(anio), int(mes))
    df = ui.tabla(filas, sesion, {"colaborador": "Colaborador", "area": "Área", "entidad": "Entidad",
                                  "inicio": "Inicio", "fin": "Fin", "dias_acumulados": "Días acumulados",
                                  "hito_superado": "Hito superado"},
                  "Ningún caso supera 90 días en este mes.")
    ui.descargar_csv(df, f"monitoreo_{int(anio)}-{int(mes):02d}.csv", "mon_csv")
    with st.expander("Ver todos los casos del mes y cuándo superarán el siguiente hito", expanded=not filas):
        ui.tabla(servicio.casos_del_mes(int(anio), int(mes)), sesion,
                 {"colaborador": "Colaborador", "entidad": "Entidad", "inicio": "Inicio", "fin": "Fin",
                  "dias_al_cierre": "Días al cierre del mes", "hito_superado": "Hito superado",
                  "proximo_hito": "Próximo hito", "supera_el": "Lo superará el"},
                 "No hay incapacidades de este tipo en el mes.")


def _rehabilitacion(sesion) -> None:
    filas = servicio.tablero_rehabilitacion()
    ui.tabla(filas, sesion, {"caso_id": "Caso", "colaborador": "Colaborador", "entidad": "Entidad",
                             "dias": "Días acumulados", "hito": "Hito", "accion": "Qué hacer",
                             "mensaje": "Detalle", "resultado": "Resultado"},
             "No hay casos activos para monitorear.")
    if not filas:
        return
    opciones = {f["caso_id"]: f"Caso {f['caso_id']} · {f['colaborador']} · {f['dias']} días" for f in filas}
    caso_id = st.selectbox("Caso", list(opciones), format_func=opciones.get, key="mon_caso")
    c1, c2, c3, c4 = st.columns(4)
    fecha = st.date_input("Fecha de la gestión", value=date.today(), key="mon_fecha")
    resultado = st.selectbox("Resultado del concepto", rm.RESULTADOS_CONCEPTO, key="mon_res")
    acciones = [
        ("Registrar solicitud a la EPS", lambda: servicio.registrar_solicitud(caso_id, fecha, sesion.usuario)),
        ("Registrar concepto emitido", lambda: servicio.registrar_emision(caso_id, fecha, resultado, sesion.usuario)),
        ("Registrar envío a la AFP", lambda: servicio.registrar_envio_afp(caso_id, fecha, sesion.usuario)),
        ("Comunicar resultado al trabajador", lambda: servicio.comunicar_resultado(caso_id, fecha, sesion.usuario)),
        ("Notificar concepto no expedido", lambda: servicio.notificar_no_expedido(caso_id, fecha, sesion.usuario)),
        ("Comunicar suspensión (>180 días)", lambda: servicio.comunicar_suspension(caso_id, fecha, sesion.usuario)),
    ]
    columnas = [c1, c2, c3, c4, c1, c2]
    for (texto, accion), col in zip(acciones, columnas):
        if col.button(texto, key=f"mon_{texto}"):
            try:
                accion()
                ui.flash("success", f"Listo: {texto.lower()}.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))


def _reintegros(sesion) -> None:
    st.caption("Después del día 180 la empresa deja de pagar por nómina y el pago lo gestiona el trabajador ante el "
               "fondo de pensiones o la EPS (5.5.3). Aquí se anota ese dinero de las incapacidades de más de 180 "
               "días. NO es el pago de la EPS a la empresa: ese se registra en Conciliación. El procedimiento "
               "solo dice «reintegro de los pagos de incapacidades superiores a 180 días realizadas por las EPS a "
               "los trabajadores»; conviene confirmar con Gestión Humana a quién se reintegra.")
    ui.tabla(ui.con_moneda(servicio.listar_reintegros(), "valor"), sesion,
             {"colaborador": "Colaborador", "fecha": "Fecha", "valor": "Valor",
              "entidad_pagadora": "Pagó", "nota": "Nota"}, "Sin reintegros registrados.")
    candidatas = [i for i in consultas.listar_incapacidades()
                  if consultas.acumulado_caso_a_fecha(consultas.caso_id_de(i["id"]), i["fecha_fin"]) > 180]
    if not candidatas:
        st.caption("No hay casos con más de 180 días acumulados.")
        return
    inc_id = ui.selector_incapacidad(candidatas, "mon_rei_sel")
    c1, c2 = st.columns(2)
    fecha = c1.date_input("Fecha del pago", value=date.today(), key="mon_rei_fecha")
    valor = c2.number_input("Valor", min_value=0.0, step=10000.0, key="mon_rei_val")
    pagadora = c1.text_input("Entidad que pagó (EPS / fondo de pensiones)", key="mon_rei_ent")
    nota = c2.text_input("Nota", key="mon_rei_nota")
    if st.button("Registrar reintegro", key="mon_rei_btn"):
        try:
            servicio.registrar_reintegro(inc_id, fecha, valor, pagadora, nota, sesion.usuario)
            ui.flash("success", "Reintegro registrado.")
            st.rerun()
        except ValueError as e:
            st.error(str(e))
