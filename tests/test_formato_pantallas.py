"""El signo $ de los valores no debe romper el texto (Streamlit lo toma como fórmula si hay dos)."""
import re

import pytest
from streamlit.testing.v1 import AppTest

from core import seguridad
from modulos import REGISTRO
from tests import datos_demo

TIPOS_CON_MARKDOWN = ("markdown", "caption", "info", "warning", "error", "success")


def _pagina(clave, rol=seguridad.ROL_COORDINACION):
    def script(clave, rol):
        import importlib

        from core import database
        from core.seguridad import Sesion
        database.init_db()
        importlib.import_module(f"modulos.{clave}.interfaz").render(Sesion("u", rol))
    at = AppTest.from_function(script, args=(clave, rol), default_timeout=30)
    at.run()
    return at


def _textos(at):
    for tipo in TIPOS_CON_MARKDOWN:
        for el in at.get(tipo):
            yield el.value


@pytest.mark.parametrize("clave", [c for c, _, _ in REGISTRO])
def test_ningun_texto_tiene_dos_signos_de_dolar_sin_escapar(clave):
    datos_demo.cargar()
    at = _pagina(clave)
    assert not at.exception, at.exception
    for texto in _textos(at):
        sin_escapar = re.sub(r"\\\$", "", str(texto))
        assert sin_escapar.count("$") < 2, texto


def test_calculadora_muestra_los_totales_como_metricas():
    at = _pagina("liquidacion")
    assert not at.exception, at.exception
    metricas = {m.label: m.value for m in at.metric}
    assert metricas["Lo asume la empresa"] == "$133.333"
    assert metricas["Lo reconoce la EPS"] == "$357.333"
    assert metricas["Total al trabajador"] == "$490.667"
