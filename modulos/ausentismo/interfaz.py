"""Pantallas del módulo de ausentismo."""
from datetime import date

import streamlit as st

from core import notificaciones, ui
from modulos.ausentismo import servicio

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def render(sesion) -> None:
    st.header("📊 Reporte de ausentismo (SG-SST)")
    ui.responsables("ausentismo")
    st.caption("Paso 6 · Se envía en los primeros 3 días de cada mes. No incluye diagnósticos.")
    pend = servicio.reporte_pendiente()
    if pend:
        texto = f"Falta enviar el reporte de {MESES[pend['mes'] - 1]} {pend['anio']} (plazo: {pend['plazo']})."
        (st.error if pend["vencido"] else st.warning)(texto)
    hoy = date.today()
    c1, c2 = st.columns(2)
    anio = int(c1.number_input("Año", 2020, 2100, hoy.year, key="aus_anio"))
    mes = int(c2.selectbox("Mes", range(1, 13), index=hoy.month - 1, format_func=lambda m: MESES[m - 1], key="aus_mes"))
    ind = servicio.indicadores(anio, mes)
    t = ind["totales"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Incapacidades", t["incapacidades"])
    m2.metric("Días perdidos", t["dias_perdidos"])
    m3.metric("Colaboradores activos", t["colaboradores_activos"])
    m4.metric("Índice de ausentismo", f"{t['indice_ausentismo_pct']} %")
    for titulo, clave in (("Por tipo", "por_tipo"), ("Por entidad", "por_entidad"), ("Por área", "por_area")):
        st.subheader(titulo)
        st.dataframe(ind[clave], hide_index=True)
    with st.expander("Detalle"):
        ui.tabla(ind["detalle"].to_dict("records"), sesion)
    if sesion.rol != "SG-SST":
        _enviar(sesion, anio, mes)


def _enviar(sesion, anio: int, mes: int) -> None:
    st.subheader("Enviar el reporte por correo")
    if not notificaciones.smtp_configurado():
        st.warning("El envío de correo aún no está configurado: copie el archivo `.env.example` como "
                   "`.env` y escriba la contraseña de aplicación (ver README).")
    destinos = st.text_input("Enviar a (uno o varios correos separados por coma)",
                             value=notificaciones.ultimos_destinatarios(), key="aus_dest",
                             placeholder="pedro@gmail.com")
    st.caption("El Excel va adjunto. Contiene nombres de colaboradores: envíelo solo a personas autorizadas.")
    if st.button("Generar y enviar por correo", type="primary", key="aus_enviar"):
        try:
            _, correos = servicio.enviar_por_correo(anio, mes, destinos, sesion.usuario)
        except (ValueError, notificaciones.CorreoError) as e:
            st.error(str(e))
        else:
            ui.flash("success", "Reporte enviado a " + ", ".join(correos) + ".")
            st.rerun()
    if st.button("Solo generar el Excel y registrar el envío (sin correo)", key="aus_registrar"):
        try:
            ruta = servicio.registrar_envio(anio, mes, sesion.usuario)
            ui.flash("success", f"Reporte generado en {ruta} y registrado en notificaciones.")
            st.rerun()
        except ValueError as e:
            st.error(str(e))
