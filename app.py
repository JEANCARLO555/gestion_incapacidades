"""
Gestión de incapacidades · punto de entrada.

Ejecutar con:   streamlit run app.py
"""
import importlib
import streamlit as st
import pandas as pd

from config import responsables
from core import auditoria, database, notificaciones, seguridad, ui
from modulos import REGISTRO

st.set_page_config(page_title="Gestión de incapacidades", page_icon="🩺", layout="wide")
database.init_db()

# --------------------------------------------------------------- barra lateral
st.sidebar.title("🩺 Incapacidades")
usuario = st.sidebar.text_input("Usuario", value="usuario", key="app_usuario").strip() or "usuario"
rol = st.sidebar.selectbox("Rol", seguridad.ROLES, index=1, key="app_rol")
sesion = seguridad.Sesion(usuario, rol)
st.sidebar.caption("⚠️ Sin inicio de sesión real: el rol se elige a mano (ver README).")

menu = {clave: etiqueta for clave, etiqueta, _ in REGISTRO if seguridad.puede_ver_modulo(rol, clave)}
menu["_proceso"] = "📋 Proceso (16 pasos)"
menu["_notificaciones"] = "📨 Notificaciones"

if rol in seguridad.ROLES_VEN_AUDITORIA:
    menu["_auditoria"] = "🕵️ Auditoría"
pagina = st.sidebar.radio("Módulo", list(menu), format_func=menu.get, key="app_pagina")

ui.mostrar_flash()


# --------------------------------------------------------------- páginas de apoyo
def pagina_notificaciones() -> None:
    st.header("📨 Bandeja de notificaciones")
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
    st.header("📋 Proceso de incapacidades (16 pasos)")
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
    st.header("🕵️ Auditoría")
    ui.tabla(auditoria.listar(), sesion, {"fecha": "Fecha", "usuario": "Usuario", "rol": "Rol",
                                          "accion": "Acción", "entidad": "Entidad",
                                          "entidad_id": "N.º", "detalle": "Detalle"}, "Sin registros.")


# --------------------------------------------------------------- despacho
if pagina == "_proceso":
    pagina_proceso()
elif pagina == "_notificaciones":
    pagina_notificaciones()
elif pagina == "_auditoria":
    pagina_auditoria()
else:
    importlib.import_module(f"modulos.{pagina}.interfaz").render(sesion)