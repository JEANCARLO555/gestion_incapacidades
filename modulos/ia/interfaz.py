"""Pantallas del módulo de análisis con IA."""
import random
import sqlite3
from datetime import date, timedelta
import streamlit as st
import pandas as pd
from core import ui, notificaciones
from modulos.ia import servicio
from generador import procesar_orden, enviar_correo_smtp


def generar_colaboradores_rapido(cantidad: int):
    """Genera colaboradores ficticios al instante con documento de identidad obligatorio."""
    nombres = ["Carlos", "Ana", "Luis", "María", "Javier", "Diana", "Andrés", "Sofía", "Juan", "Laura"]
    apellidos = ["Gómez", "Rodríguez", "Pérez", "López", "Martínez", "García", "Torres", "Vargas"]
    areas = ["Operaciones", "Gestión Humana", "Administración", "Finanzas", "Comercial"]

    colabs = []
    for _ in range(cantidad):
        nom = f"{random.choice(nombres)} {random.choice(apellidos)}"
        area = random.choice(areas)
        doc = str(random.randint(100000000, 1099999999))
        correo = f"{nom.lower().replace(' ', '.')}@empresa.com"
        colabs.append({"nombre": nom, "documento": doc, "area": area, "correo": correo})
    return colabs


def a_texto(datos):
    """Formatea la información de DataFrames y listas para la IA."""
    if isinstance(datos, pd.DataFrame):
        return datos.to_string(index=False)
    elif isinstance(datos, list):
        return pd.DataFrame(datos).to_string(index=False) if datos else "Sin registros"
    return str(datos)


def render(sesion) -> None:
    st.header("🤖 Análisis de información con IA")
    ui.responsables("ia")
    st.caption("Panel de indicadores y Asistente IA para análisis de información y ejecución de órdenes.")

    # --- LECTURA DE INFORMACIÓN DEL SISTEMA DESDE BD ---
    df_entidades = servicio.indicadores_por_entidad()
    df_ausentismo = servicio.ausentismo_por_area()
    df_anomalias = servicio.anomalias()

    # Tablas e indicadores
    st.subheader("Rechazos y tiempos de pago por entidad")
    st.dataframe(df_entidades, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Ausentismo por área")
        st.dataframe(df_ausentismo, hide_index=True)
    with col2:
        st.subheader("Datos atípicos para revisar")
        ui.tabla(df_anomalias, sesion, {"tipo": "Tipo", "colaborador": "Colaborador", "detalle": "Detalle"},
                 "No se detectaron datos atípicos.")

    st.divider()

    # --- CONTEXTO SINTETIZADO PARA CONSULTAS ---
    contexto_completo = f"""
    ENTIDADES:
    {a_texto(df_entidades)}
    AUSENTISMO POR ÁREA:
    {a_texto(df_ausentismo)}
    ANOMALÍAS RECIENTES:
    {a_texto(df_anomalias)}
    """

    # --- CAJA DE COMANDO IA ---
    st.subheader("🧠 Asistente Inteligente")
    
    pregunta = st.text_input(
        "Ingresa cualquier orden o consulta (ej: 'Cualquier Persona generó incapacidad de 3 días', 'analiza el ausentismo'):",
        key="ia_preg_input"
    )
    
    if st.button("Ejecutar / Analizar", type="primary", key="btn_ejecutar_ia"):
        if not pregunta.strip():
            st.warning("Por favor ingrese una instrucción.")
        else:
            with st.spinner("Procesando consulta o creando registro..."):
                resultado = procesar_orden(pregunta, contexto_datos=contexto_completo)
                st.session_state["resultado_ia_persistente"] = resultado

    # --- DESPACHADOR DE ACCIONES PERSISTENTES EN BD ---
    if "resultado_ia_persistente" in st.session_state:
        res = st.session_state["resultado_ia_persistente"]
        accion = res.get("accion") if isinstance(res, dict) else None

        # 1. ANÁLISIS E INFORMES
        if accion == "analisis":
            st.subheader(f"📊 {res.get('titulo', 'Informe de Análisis de Información')}")
            st.info(f"**Conclusión:** {res.get('conclusion', '')}")

            puntos = res.get("puntos_clave", [])
            if puntos:
                st.write("**Puntos Clave Detectados:**")
                for punto in puntos:
                    st.write(f"• {punto}")

            if "recomendacion" in res:
                st.success(f"💡 **Recomendación:** {res.get('recomendacion')}")

        # 2. CREACIÓN MASIVA DE USUARIOS
        elif accion == "crear_colaboradores":
            cantidad = int(res.get("cantidad", 5))
            colaboradores = res.get("datos") or generar_colaboradores_rapido(cantidad)
            
            try:
                conn = sqlite3.connect("data/incapacidades.db")
                cursor = conn.cursor()
                for c in colaboradores:
                    doc = c.get("documento") or str(random.randint(100000000, 1099999999))
                    try:
                        cursor.execute("INSERT INTO colaboradores (nombre, documento, area, correo) VALUES (?, ?, ?, ?)",
                                       (c["nombre"], doc, c.get("area", "General"), c.get("correo", "")))
                    except sqlite3.OperationalError:
                        cursor.execute("INSERT INTO colaboradores (nombre, documento) VALUES (?, ?)", (c["nombre"], doc))

                conn.commit()
                conn.close()
                st.success(f"✅ Se guardaron {len(colaboradores)} nuevos usuarios en la BD.")
                st.dataframe(pd.DataFrame(colaboradores), use_container_width=True)
                st.info("🔄 Revisa los módulos **Ausentismo SG-SST** o **Novedades de nómina** para ver los usuarios cargados.")
            except Exception as e:
                st.error(f"Error al guardar usuarios: {e}")

        # 3. REGISTRO DE INCAPACIDAD AJUSTADO CON canal_recepcion
        elif accion == "registrar_incapacidad":
            persona = res.get("colaborador", "Usuario General")
            dias = int(res.get("dias", 1))
            tipo = res.get("tipo", "Enfermedad general")
            entidad = res.get("entidad", "SURA EPS")

            try:
                fecha_inicio = date.today().strftime("%Y-%m-%d")
                fecha_fin = (date.today() + timedelta(days=dias - 1)).strftime("%Y-%m-%d")

                conn = sqlite3.connect("data/incapacidades.db")
                cursor = conn.cursor()

                # A. Buscar o crear el colaborador en la BD
                cursor.execute("SELECT id FROM colaboradores WHERE nombre LIKE ?", (f"%{persona}%",))
                colab_row = cursor.fetchone()

                if colab_row:
                    colaborador_id = colab_row[0]
                else:
                    doc_auto = str(random.randint(100000000, 1099999999))
                    try:
                        cursor.execute("INSERT INTO colaboradores (nombre, documento, area, correo) VALUES (?, ?, ?, ?)",
                                       (persona, doc_auto, "General", f"{persona.lower().replace(' ', '.')}@empresa.com"))
                    except sqlite3.OperationalError:
                        cursor.execute("INSERT INTO colaboradores (nombre, documento) VALUES (?, ?)", (persona, doc_auto))
                    colaborador_id = cursor.lastrowid

                # B. Inserción incluyendo la columna canal_recepcion requerida por la BD
                try:
                    cursor.execute("""
                        INSERT INTO incapacidades 
                        (colaborador_id, tipo, entidad, fecha_inicio, fecha_fin, dias, canal_recepcion, fecha_recepcion, estado, reemplazo)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (colaborador_id, tipo, entidad, fecha_inicio, fecha_fin, dias, "Recepción", fecha_inicio, "Recibida", "Por asignar"))
                except sqlite3.OperationalError:
                    # En caso de esquema alternativo
                    cursor.execute("""
                        INSERT INTO incapacidades 
                        (colaborador_id, tipo, entidad, fecha_inicio, fecha_fin, dias, estado)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (colaborador_id, tipo, entidad, fecha_inicio, fecha_fin, dias, "Recibida"))

                conn.commit()
                conn.close()

                st.success(f"📋 **Incapacidad registrada en la BD para `{persona}` ({dias} días).**")
                st.info("📥 **Sincronización:** Ve al módulo **Recepción** (pestaña **'Recibidas'**) para ver el reporte reflejado en tiempo real.")

            except Exception as e:
                st.error(f"Error al escribir en la base de datos: {e}")

        # 4. ELIMINACIÓN DE REGISTROS
        elif accion == "eliminar_colaborador":
            target = res.get("target") or "registro seleccionado"
            try:
                conn = sqlite3.connect("data/incapacidades.db")
                cursor = conn.cursor()
                cursor.execute("DELETE FROM incapacidades WHERE colaborador_id IN (SELECT id FROM colaboradores WHERE nombre LIKE ?)", (f"%{target}%",))
                conn.commit()
                conn.close()
                st.success(f"✅ Registros asociados a `{target}` fueron eliminados.")
            except Exception as e:
                st.error(f"No se pudo eliminar de la BD: {e}")

        # 5. ENVÍO DE CORREOS SMTP
        elif accion == "correo":
            destinatario = res.get("destinatario", "")
            asunto = res.get("asunto", "Notificación del Sistema")
            cuerpo = res.get("mensaje", "")

            st.success("✅ Borrador generado por la IA")
            st.write(f"**Para:** `{destinatario if destinatario else 'No detectado'}`")
            st.write(f"**Asunto:** {asunto}")
            st.info(cuerpo)

            if destinatario and "@" in destinatario:
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("🚀 Enviar Correo Ahora", type="primary"):
                        with st.spinner("Enviando vía SMTP..."):
                            ok, msg = enviar_correo_smtp(destinatario, asunto, cuerpo)
                            if ok:
                                st.success(f"¡{msg}!")
                                del st.session_state["resultado_ia_persistente"]
                            else:
                                st.error(msg)
                with col_btn2:
                    if st.button("📨 Guardar en Notificaciones"):
                        notificaciones.guardar(
                            categoria="Incapacidad / IA",
                            destinatario_tipo="Correo",
                            destinatario=destinatario,
                            asunto=asunto,
                            mensaje=cuerpo
                        )
                        st.success("Guardado en la bandeja de notificaciones pendientes.")
                        del st.session_state["resultado_ia_persistente"]
            else:
                st.error("No se detectó un correo electrónico válido.")

        # 6. RESPUESTA A PREGUNTAS / CONSULTAS DE ANÁLISIS
        elif accion == "consulta":
            st.subheader("💡 Respuesta / Análisis:")
            st.write(res.get("respuesta", ""))

        # 7. OTROS REPORTES
        else:
            st.success(f"⚙️ **{res.get('titulo', 'Instrucción procesada')}**")
            st.write(res.get("detalle") or res.get("mensaje") or "Procesado correctamente.")