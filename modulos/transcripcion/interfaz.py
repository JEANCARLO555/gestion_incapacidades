"""Pantallas del módulo de transcripción."""
from datetime import date

import streamlit as st

from config import settings
from core import flujo, ui
from modulos.transcripcion import servicio


def render(sesion) -> None:
    st.header("🖥️ Transcripción ante la EPS / ARL")
    ui.responsables("transcripcion")
    st.caption("Procedimiento 5.2 · Plazos de la tabla 5.2.1.")
    filas = servicio.por_transcribir()
    if not filas:
        st.success("No hay incapacidades pendientes de transcribir.")
        return
    for f in filas:
        f["limite_txt"] = str(f["fecha_limite"]) if f["fecha_limite"] else "—"
        f["restantes_txt"] = "—" if f["dias_restantes"] is None else f["dias_restantes"]
        f["via"] = "Correo / presencial" if f["manual"] else "Portal"
    ui.tabla(filas, sesion, {"id": "N.º", "colaborador": "Colaborador", "entidad": "Entidad",
                             "tipo": "Tipo", "plazo": "Plazo", "limite_txt": "Fecha límite",
                             "restantes_txt": "Días restantes", "via": "Vía", "estado": "Estado"})
    vencidas = [f for f in filas if f["vencido"]]
    if vencidas:
        st.error(f"{len(vencidas)} incapacidad(es) con el plazo de transcripción vencido.")

    st.subheader("Registrar transcripción")
    inc_id = ui.selector_incapacidad(filas, "tra_sel")
    elegida = next(f for f in filas if f["id"] == inc_id)
    if elegida["manual"]:
        st.info(f"{elegida['entidad']}: la transcripción se hace por correo electrónico y con "
                "personal de la entidad.")
    c1, c2 = st.columns(2)
    fecha = c1.date_input("Fecha de transcripción", value=date.today(), key="tra_fecha")
    medio = c2.selectbox("Medio", settings.MEDIOS_TRANSCRIPCION, key="tra_medio")
    radicado = c1.text_input("N.º de radicado", key="tra_rad")
    evidencia = c2.text_input("Evidencia (captura, correo enviado, ruta)", key="tra_evi")
    nota = st.text_area("Nota", key="tra_nota")
    if st.button("Registrar transcripción", type="primary", key="tra_btn"):
        try:
            r = servicio.registrar_transcripcion(inc_id, fecha, medio, radicado,
                                                 sesion.usuario, evidencia, nota)
        except (ValueError, flujo.FlujoError) as e:
            st.error(str(e))
            return
        ui.flash("warning" if r["fuera_de_plazo"] else "success",
                 "Transcrita (FUERA DE PLAZO)." if r["fuera_de_plazo"] else "Incapacidad transcrita.")
        st.rerun()
