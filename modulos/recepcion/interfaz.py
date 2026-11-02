"""Pantallas del módulo de recepción."""
from datetime import date

import streamlit as st

from config import reglas_documentos as rd, settings
from core import consultas, seguridad, ui
from modulos.recepcion import servicio

COLUMNAS = {"id": "N.º", "colaborador": "Colaborador", "tipo": "Tipo", "entidad": "Entidad",
            "fecha_inicio": "Inicio", "fecha_fin": "Fin", "dias": "Días",
            "canal_recepcion": "Canal", "fecha_recepcion": "Recibida", "estado": "Estado",
            "reemplazo": "Reemplazo"}


def render(sesion) -> None:
    st.header("📥 Recepción de incapacidades")
    ui.responsables("recepcion")
    st.caption("Procedimiento 5.1.1 · Registrar lo que llega y por qué canal.")
    tab_reg, tab_lista, tab_col = st.tabs(["Registrar incapacidad", "Recibidas", "Colaboradores"])
    with tab_reg:
        _registrar(sesion)
    with tab_lista:
        _recibidas(sesion)
    with tab_col:
        _colaboradores(sesion)


def _registrar(sesion) -> None:
    colaboradores = consultas.listar_colaboradores()
    if not colaboradores:
        st.info("Primero registre al colaborador en la pestaña «Colaboradores».")
        return
    v = st.session_state.setdefault("rec_v", 0)
    opciones = {c["id"]: f"{c['nombre']} · {c['documento']}" for c in colaboradores}
    colaborador_id = st.selectbox("Colaborador", list(opciones), format_func=opciones.get,
                                  key=f"rec_col_{v}")
    c1, c2 = st.columns(2)
    tipo = c1.selectbox("Tipo", rd.TIPOS_INCAPACIDAD, key=f"rec_tipo_{v}")
    entidad = c2.selectbox("Entidad (EPS / ARL)", settings.ENTIDADES, key=f"rec_ent_{v}")
    ini = c1.date_input("Fecha de inicio", value=date.today(), key=f"rec_ini_{v}")
    fin = c2.date_input("Fecha de fin", value=date.today(), key=f"rec_fin_{v}")
    if fin < ini:
        st.error("La fecha de fin no puede ser anterior a la de inicio.")
        return
    dias = (fin - ini).days + 1
    st.write(f"Días de incapacidad: **{dias}**")

    nacimiento = None
    if tipo == rd.TIPO_LICENCIA_PATERNIDAD:
        nacimiento = st.date_input("Fecha de nacimiento del hijo", value=date.today(),
                                   key=f"rec_nac_{v}")

    candidatas = servicio.candidatas_a_prorroga(colaborador_id)
    prorroga_de = None
    if candidatas:
        mapa = {None: "No es prórroga"} | {c["id"]: ui.etiqueta_incapacidad(c) for c in candidatas}
        prorroga_de = st.selectbox("¿Es prórroga de otra incapacidad?", list(mapa),
                                   format_func=mapa.get, key=f"rec_pro_{v}")

    st.subheader("Cómo llegó")
    c3, c4 = st.columns(2)
    canal = c3.selectbox("Canal de recepción", settings.CANALES_RECEPCION, key=f"rec_canal_{v}")
    recibido_por = c4.text_input("Recibida por", value=sesion.usuario, key=f"rec_por_{v}")
    fecha_recepcion = c3.date_input("Fecha de recepción", value=date.today(), key=f"rec_frec_{v}")
    informo_jefe = c4.checkbox("El colaborador informó al jefe inmediato", key=f"rec_jefe_{v}")
    llegada_fisica = c4.checkbox("La documentación física ya llegó", key=f"rec_fis_{v}")

    st.subheader("Documentos entregados")
    requeridos = servicio.documentos_requeridos(tipo, ini, fin)
    entregados = [d for d in requeridos
                  if st.checkbox(d, key=f"rec_doc_{v}_{tipo}_{dias > 2}_{d}")]
    obs = st.text_area("Observaciones", key=f"rec_obs_{v}")

    for aviso in servicio.advertencias(canal, llegada_fisica, informo_jefe, ini, fecha_recepcion):
        st.warning(aviso)

    if st.button("Guardar recepción", type="primary", key=f"rec_guardar_{v}"):
        try:
            inc_id = servicio.registrar_incapacidad(
                colaborador_id, tipo, entidad, ini, fin, canal, recibido_por, informo_jefe,
                llegada_fisica, entregados, fecha_recepcion, obs, prorroga_de, nacimiento,
                usuario=sesion.usuario)
        except ValueError as e:
            st.error(str(e))
            return
        st.session_state["rec_v"] = v + 1
        ui.flash("success", f"Incapacidad #{inc_id} registrada. Pasa a verificación documental.")
        st.rerun()


def _recibidas(sesion) -> None:
    filas = servicio.listar(sesion)
    vacio = "Aún no hay incapacidades registradas."
    if sesion.rol == seguridad.ROL_LIDER:
        fuera = servicio.cantidad_fuera_del_equipo(sesion)
        vacio = (f"Como líder solo ves las incapacidades de las personas cuyo «Jefe inmediato» sea "
                 f"«{sesion.usuario}» (no importan mayúsculas, tildes ni espacios). "
                 + (f"Hay {fuera} incapacidad(es) registradas que no son de tu equipo. Si deberían serlo, "
                    "cambia tu usuario en la barra lateral para que coincida, o pide que corrijan el "
                    "«Jefe inmediato» del colaborador (Colaboradores → Editar)." if fuera
                    else "Todavía no hay incapacidades registradas."))
    df = ui.tabla(filas, sesion, COLUMNAS, vacio)
    ui.descargar_csv(df, "incapacidades_recibidas.csv", "rec_csv")
    if filas and sesion.rol != "Recepcionista":
        st.subheader("Asignar reemplazo")
        inc_id = ui.selector_incapacidad(filas, "rec_reemplazo_sel")
        nombre = st.text_input("Persona que reemplaza", key="rec_reemplazo_txt")
        if st.button("Guardar reemplazo", key="rec_reemplazo_btn"):
            try:
                servicio.asignar_reemplazo(inc_id, nombre, sesion.usuario)
                ui.flash("success", "Reemplazo registrado.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))


def _colaboradores(sesion) -> None:
    with st.form("rec_form_colaborador", clear_on_submit=True):
        c1, c2 = st.columns(2)
        documento = c1.text_input("Documento de identidad")
        nombre = c2.text_input("Nombre completo")
        cargo = c1.text_input("Cargo")
        area = c2.text_input("Área")
        jefe = c1.text_input("Jefe inmediato (nombre de usuario del líder)")
        correo = c2.text_input("Correo")
        ibc = c1.number_input("IBC mensual (Ingreso Base de Cotización)", min_value=0.0,
                              step=100000.0, help="Sin IBC el sistema no puede calcular lo que paga la EPS.")
        if st.form_submit_button("Guardar colaborador"):
            try:
                servicio.registrar_colaborador(documento, nombre, cargo, area, jefe, correo, ibc,
                                               sesion.usuario)
                ui.flash("success", "Colaborador registrado.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    colaboradores = consultas.listar_colaboradores()
    ui.tabla(colaboradores, sesion,
             {"documento": "Documento", "nombre": "Nombre", "cargo": "Cargo", "area": "Área",
              "jefe_inmediato": "Jefe inmediato", "ibc": "IBC"})
    if colaboradores:
        with st.expander("Editar un colaborador (por ejemplo, corregir el IBC)"):
            mapa = {c["id"]: f"{c['nombre']} · {c['documento']}" for c in colaboradores}
            cid = st.selectbox("Colaborador", list(mapa), format_func=mapa.get, key="rec_ed_sel")
            c = next(x for x in colaboradores if x["id"] == cid)
            e1, e2 = st.columns(2)
            nuevo_ibc = e1.number_input("IBC mensual", min_value=0.0, step=100000.0, value=float(c["ibc"]),
                                        key=f"rec_ed_ibc_{cid}")
            nuevo_jefe = e2.text_input("Jefe inmediato", value=c["jefe_inmediato"] or "", key=f"rec_ed_jefe_{cid}")
            nuevo_area = e1.text_input("Área", value=c["area"] or "", key=f"rec_ed_area_{cid}")
            nuevo_correo = e2.text_input("Correo", value=c["correo"] or "", key=f"rec_ed_correo_{cid}")
            if st.button("Guardar cambios", key=f"rec_ed_btn_{cid}"):
                try:
                    servicio.actualizar_colaborador(cid, ibc=nuevo_ibc, jefe_inmediato=nuevo_jefe,
                                                    area=nuevo_area, correo=nuevo_correo, usuario=sesion.usuario)
                    ui.flash("success", "Colaborador actualizado.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
