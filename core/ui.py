"""Pequeñas ayudas de Streamlit que repiten todas las pantallas."""
import pandas as pd
import streamlit as st

from config import responsables as resp_cfg
from core import seguridad
from core.utils import moneda


def flash(nivel: str, texto: str) -> None:
    """Guarda un mensaje para mostrarlo después de recargar la pantalla."""
    st.session_state["_flash"] = (nivel, texto)


def mostrar_flash() -> None:
    mensaje = st.session_state.pop("_flash", None)
    if mensaje:
        getattr(st, mensaje[0])(mensaje[1])


def tabla(filas: list[dict], sesion, columnas: dict | None = None, vacio: str = "Sin registros."):
    """Muestra una tabla; `columnas` = {columna_bd: 'Título'} define cuáles y cómo se ven."""
    if not filas:
        st.info(vacio)
        return pd.DataFrame()
    df = seguridad.filtrar_columnas(pd.DataFrame(filas), sesion.rol)
    if columnas:
        df = df[[c for c in columnas if c in df.columns]].rename(columns=columnas)
    st.dataframe(df, hide_index=True)
    return df


def etiqueta_incapacidad(i: dict) -> str:
    return (f"#{i['id']} · {i['colaborador']} · {i['tipo']} · {i['entidad']} · "
            f"{i['fecha_inicio']} → {i['fecha_fin']} · {i['estado']}")


def selector_incapacidad(filas: list[dict], key: str, etiqueta: str = "Incapacidad"):
    """Lista desplegable de incapacidades; devuelve el id elegido o None."""
    if not filas:
        return None
    opciones = {f["id"]: etiqueta_incapacidad(f) for f in filas}
    return st.selectbox(etiqueta, list(opciones), format_func=opciones.get, key=key)


def descargar_csv(df: pd.DataFrame, nombre: str, key: str) -> None:
    if df is not None and not df.empty:
        st.download_button("⬇️ Descargar CSV", df.to_csv(index=False).encode("utf-8-sig"),
                           file_name=nombre, mime="text/csv", key=key)


def responsables(modulo: str) -> None:
    """Muestra, plegado, quién es el responsable según la tabla 7 del procedimiento."""
    pasos = resp_cfg.pasos_de_modulo(modulo)
    with st.expander("👤 ¿Quién es responsable según el procedimiento?"):
        if not pasos:
            st.write(resp_cfg.nota_sin_pasos(modulo))
            return
        st.dataframe(pd.DataFrame([{"Paso": p["no"], "Actividad": p["actividad"],
                                    "Responsable": ", ".join(p["responsables"])} for p in pasos]),
                     hide_index=True)
        st.caption("Si el responsable es el colaborador o Gestión documental, esa parte ocurre fuera de la "
                   "aplicación. Más detalle en «Proceso (16 pasos)».")


def con_moneda(filas: list[dict], *campos: str) -> list[dict]:
    """Copia de las filas con esos campos escritos como dinero ($1.234.567; vacío = —)."""
    return [{**f, **{c: moneda(f[c]) for c in campos if c in f}} for f in filas]
