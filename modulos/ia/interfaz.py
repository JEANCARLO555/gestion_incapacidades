"""Pantallas del módulo de análisis con IA."""
import streamlit as st

from core import ui
from modulos.ia import servicio


def render(sesion) -> None:
    st.header("🤖 Análisis de información")
    ui.responsables("ia")
    st.caption("Indicadores locales y, de forma opcional, preguntas a un modelo de IA con datos "
               "agregados y anónimos (nunca nombres ni diagnósticos).")
    st.subheader("Rechazos y tiempos de pago por entidad")
    st.dataframe(servicio.indicadores_por_entidad(), hide_index=True)
    st.subheader("Ausentismo por área")
    st.dataframe(servicio.ausentismo_por_area(), hide_index=True)
    st.subheader("Datos atípicos para revisar")
    ui.tabla(servicio.anomalias(), sesion, {"tipo": "Tipo", "colaborador": "Colaborador", "detalle": "Detalle"},
             "No se detectaron datos atípicos.")
    st.subheader("Pregunte a la IA")
    if not servicio.ia_disponible():
        st.info("Para activar esta sección defina la variable de entorno ANTHROPIC_API_KEY.")
    pregunta = st.text_input("Pregunta (por ejemplo: ¿qué entidad rechaza más?)", key="ia_preg")
    if st.button("Consultar", key="ia_btn") and pregunta:
        with st.spinner("Consultando..."):
            try:
                st.write(servicio.consultar(pregunta))
            except Exception as e:  # error de red o de la API: se muestra sin romper la pantalla
                st.error(f"No se pudo consultar: {e}")
