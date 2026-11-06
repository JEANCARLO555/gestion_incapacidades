"""
Gestión de incapacidades · punto de entrada con autenticación e iconos.

Ejecutar con:   streamlit run app.py
"""
import importlib
import streamlit as st
import pandas as pd

from config import responsables
from core import auditoria, database, notificaciones, seguridad, ui
from modulos import REGISTRO

st.set_page_config(page_title="Gestión de incapacidades", page_icon=":material/health_and_safety:", layout="wide")
database.init_db()

# --------------------------------------------------------------- 1. Estado de Sesión (Login / Registro)
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = ""
if "rol_actual" not in st.session_state:
    st.session_state.rol_actual = ""

if not st.session_state.autenticado:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><h2 style='text-align: center;'>MediCampus</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748b;'>Sistema de Gestión de Incapacidades</p>", unsafe_allow_html=True)
        
        tab_login, tab_registro = st.tabs([":material/key: Iniciar Sesión", ":material/edit_note: Crear Cuenta"])
        
        with tab_login:
            with st.form("form_login"):
                usuario_input = st.text_input("Usuario", key="login_user")
                password_input = st.text_input("Contraseña", type="password", key="login_pass")
                rol_input = st.selectbox("Rol de ingreso", seguridad.ROLES, index=1, key="login_rol")
                btn_ingresar = st.form_submit_button("Ingresar al Sistema", use_container_width=True)
                
                if btn_ingresar:
                    if usuario_input.strip() and password_input.strip():
                        st.session_state.autenticado = True
                        st.session_state.usuario_actual = usuario_input.strip()
                        st.session_state.rol_actual = rol_input
                        st.rerun()
                    else:
                        st.error("Ingrese su usuario y contraseña.")

        with tab_registro:
            with st.form("form_registro"):
                reg_usuario = st.text_input("Nuevo Usuario", key="reg_user")
                reg_email = st.text_input("Correo electrónico", key="reg_email")
                reg_pass = st.text_input("Contraseña", type="password", key="reg_pass")
                reg_rol = st.selectbox("Asignar Rol", seguridad.ROLES, key="reg_rol")
                btn_registrar = st.form_submit_button("Crear Cuenta", use_container_width=True)
                
                if btn_registrar:
                    if reg_usuario.strip() and reg_pass.strip():
                        st.success(f"Cuenta para '{reg_usuario}' registrada con éxito. Ya puede iniciar sesión.")
                    else:
                        st.warning("Complete los campos obligatorios.")

    st.stop()

# --------------------------------------------------------------- 2. Barra Lateral y Sesión Activa
usuario = st.session_state.usuario_actual
rol = st.session_state.rol_actual
sesion = seguridad.Sesion(usuario, rol)

st.sidebar.title("Incapacidades")
st.sidebar.caption(f"Usuario: **{usuario}** | Rol: **{rol}**")

if st.sidebar.button(":material/logout: Cerrar Sesión", use_container_width=True):
    st.session_state.autenticado = False
    st.session_state.usuario_actual = ""
    st.session_state.rol_actual = ""
    st.rerun()

st.sidebar.markdown("---")

# Construcción dinámica del menú manteniendo la lógica exacta del script original
menu = {clave: etiqueta for clave, etiqueta, _ in REGISTRO if seguridad.puede_ver_modulo(rol, clave)}
menu["_proceso"] = "Proceso (16 pasos)"
menu["_notificaciones"] = "Notificaciones"

if rol in seguridad.ROLES_VEN_AUDITORIA:
    menu["_auditoria"] = "Auditoría"

pagina = st.sidebar.radio("Módulo", list(menu), format_func=menu.get, key="app_pagina")

ui.mostrar_flash()


# --------------------------------------------------------------- 3. Páginas de Apoyo (Originales)
def pagina_notificaciones() -> None:
    st.header("Bandeja de notificaciones")
    st.caption("Correos generados por el sistema. Si no hay SMTP configurado, copie el texto y envíelo "
               "desde su correo; luego márquelo como enviado.")
    filas = notificaciones.listar()
    pendientes = [f for f in filas if f["estado"] == "Pendiente"]
    st.metric("Pendientes de envío", len(pendientes))
    if notificaciones.smtp_configurado() and pendientes and st.button("Enviar pendientes por correo"):
        r = notificaciones.enviar_pendientes()
        ui.flash("info", f"Enviadas: {r['enviadas']} · errores: {r['errores']}")
        st.rerun()
    ui.tabla(filas, sesion, {"id": "N.º", "creado_en": "Creada", "categoria": "Categoría",
                             "destinatario_tipo": "Para", "destinatario": "Destinatario",
                             "asunto": "Asunto", "estado": "Estado"}, "No hay notificaciones.")
    if filas:
        elegida = st.selectbox("Ver notificación", [f["id"] for f in filas],
                               format_func=lambda i: next(f"#{f['id']} · {f['asunto']}" for f in filas if f["id"] == i))
        n = next(f for f in filas if f["id"] == elegida)
        st.text_area("Mensaje", n["mensaje"], height=240, key=f"noti_{elegida}")
        if n["estado"] == "Pendiente" and st.button("Marcar como enviada"):
            notificaciones.marcar_enviada(elegida)
            st.rerun()


def pagina_proceso() -> None:
    st.header("Proceso de incapacidades (16 pasos)")
    st.caption("Tabla «7. Desarrollo» del procedimiento: qué se hace, quién es el responsable y dónde se "
               "hace en la aplicación.")
    propio = seguridad.RESPONSABLE_EN_PROCEDIMIENTO.get(rol)
    solo_mios = False
    if propio:
        solo_mios = st.checkbox(f"Mostrar solo los pasos donde el responsable es «{propio}»", key="proc_mios")
    pasos = responsables.pasos_de_responsable(propio) if solo_mios else responsables.PASOS
    st.dataframe(pd.DataFrame([{"Paso": p["no"], "Actividad": p["actividad"],
                                "Responsable": ", ".join(p["responsables"]), "Qué se hace": p["descripcion"],
                                "En la aplicación": p["en_app"]} for p in pasos]), hide_index=True)
    st.subheader("Roles de la aplicación y de dónde salen")
    st.dataframe(pd.DataFrame([{"Rol": r, "Qué hace en la aplicación": seguridad.DESCRIPCION_ROL[r][0],
                                "Dónde aparece en el procedimiento": seguridad.DESCRIPCION_ROL[r][1]}
                               for r in seguridad.ROLES]), hide_index=True)
    st.info("Responsables de la tabla que NO tienen rol en la aplicación: **Colaborador** (pasos 1, 3 y 5: informa "
            "y entrega los documentos, y quien los registra es la recepción) y **Gestión documental** (paso 16: "
            "recibe el archivo físico). Esos pasos ocurren fuera de la aplicación.")


def pagina_auditoria() -> None:
    st.header("Auditoría")
    ui.tabla(auditoria.listar(), sesion, {"fecha": "Fecha", "usuario": "Usuario", "rol": "Rol",
                                          "accion": "Acción", "entidad": "Entidad",
                                          "entidad_id": "N.º", "detalle": "Detalle"}, "Sin registros.")


# --------------------------------------------------------------- 4. Despacho
if pagina == "_proceso":
    pagina_proceso()
elif pagina == "_notificaciones":
    pagina_notificaciones()
elif pagina == "_auditoria":
    pagina_auditoria()
else:
    importlib.import_module(f"modulos.{pagina}.interfaz").render(sesion)