"""Humo de las pantallas: cada módulo debe abrir sin errores, vacío y con datos."""
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from core import seguridad
from modulos import REGISTRO
from tests import datos_demo

CLAVES = [c for c, _, _ in REGISTRO]


def _pagina(clave: str, rol: str):
    def script(clave, rol):
        import importlib

        from core import database
        from core.seguridad import Sesion
        database.init_db()
        importlib.import_module(f"modulos.{clave}.interfaz").render(Sesion("lider1", rol))
    at = AppTest.from_function(script, args=(clave, rol), default_timeout=30)
    at.run()
    return at


@pytest.mark.parametrize("clave", CLAVES)
def test_pantalla_vacia(clave):
    at = _pagina(clave, seguridad.ROL_COORDINACION)
    assert not at.exception, at.exception
    assert at.header


@pytest.mark.parametrize("clave", CLAVES)
def test_pantalla_con_datos(clave):
    datos_demo.cargar()
    at = _pagina(clave, seguridad.ROL_COORDINACION)
    assert not at.exception, at.exception


@pytest.mark.parametrize("rol", seguridad.ROLES)
def test_pantallas_segun_rol(rol):
    datos_demo.cargar()
    for clave in CLAVES:
        if seguridad.puede_ver_modulo(rol, clave):
            at = _pagina(clave, rol)
            assert not at.exception, (rol, clave, at.exception)


def test_recepcion_guardar_desde_la_pantalla():
    datos_demo.cargar()
    at = _pagina("recepcion", seguridad.ROL_RECEPCIONISTA)
    at.checkbox(key="rec_jefe_0").check().run()
    at.button(key="rec_guardar_0").click().run()
    assert not at.exception, at.exception
    from core import consultas
    assert len(consultas.listar_incapacidades()) == 6      # 5 de la demo + 1 nueva


def test_recepcion_crear_colaborador_desde_la_pantalla():
    at = _pagina("recepcion", seguridad.ROL_AUXILIAR)
    assert any("Colaboradores" in t.label for t in at.tabs)
    assert not at.exception


def test_app_completa_navega_por_todos_los_modulos():
    datos_demo.cargar()
    at = AppTest.from_file("../app.py", default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    clave_de = {etiqueta: clave for clave, etiqueta, _ in REGISTRO}
    clave_de |= {"📋 Proceso (16 pasos)": "_proceso", "📨 Notificaciones": "_notificaciones",
                 "🕵️ Auditoría": "_auditoria"}
    for rol in (seguridad.ROL_COORDINACION, seguridad.ROL_AUXILIAR):
        at.selectbox(key="app_rol").select(rol).run()
        etiquetas = list(at.radio(key="app_pagina").options)
        assert len(etiquetas) >= 10
        for etiqueta in etiquetas:
            at.radio(key="app_pagina").set_value(clave_de[etiqueta]).run()
            assert not at.exception, (rol, etiqueta, at.exception)


def test_seguridad_columnas_y_modulos():
    df = pd.DataFrame([{"colaborador": "A", "ibc": 1, "tipo": "x", "observaciones": "o", "documento": "1"}])
    assert list(seguridad.filtrar_columnas(df, seguridad.ROL_LIDER).columns) == ["colaborador"]
    assert "ibc" not in seguridad.filtrar_columnas(df, seguridad.ROL_RECEPCIONISTA).columns
    assert "ibc" in seguridad.filtrar_columnas(df, seguridad.ROL_AUXILIAR).columns
    assert not seguridad.puede_ver_modulo(seguridad.ROL_LIDER, "juridico")
    assert seguridad.puede_ver_modulo(seguridad.ROL_SST, "ausentismo")
    assert not seguridad.puede_ver_datos_clinicos(seguridad.ROL_CONTABILIDAD)


def test_lider_sin_equipo_ve_el_motivo():
    datos_demo.cargar()          # los colaboradores de la demo tienen de jefe a lider1 y lider2

    def script(usuario):
        from core.seguridad import ROL_LIDER, Sesion
        from modulos.recepcion import interfaz
        interfaz.render(Sesion(usuario, ROL_LIDER))
    ninguno = AppTest.from_function(script, args=("usuario",), default_timeout=30)
    ninguno.run()
    assert not ninguno.exception, ninguno.exception
    assert any("Jefe inmediato" in i.value and "«usuario»" in i.value for i in ninguno.info)
    con_equipo = AppTest.from_function(script, args=("Lider1",), default_timeout=30)
    con_equipo.run()
    assert not con_equipo.exception and len(con_equipo.dataframe) >= 1
