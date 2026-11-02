"""El caso de las capturas: una incapacidad de 257 días (2026-11-01 a 2027-07-15) con IBC de $500.000."""
from datetime import date

import pytest
from streamlit.testing.v1 import AppTest

from config import reglas_documentos as rd
from core import consultas
from modulos.monitoreo import servicio as monitoreo
from modulos.recepcion import servicio as recepcion


@pytest.fixture
def jean():
    cid = recepcion.registrar_colaborador("1", "jean", area="Ventas", ibc=500_000)
    return recepcion.registrar_incapacidad(cid, rd.TIPO_ENFERMEDAD_GENERAL, "Salud Total", date(2026, 11, 1),
                                           date(2027, 7, 15), "Recepción", "r", True, True,
                                           [rd.DOC_CERTIFICADO, rd.DOC_EPICRISIS])


def test_liquidacion_de_257_dias(jean):
    r = consultas.resumen_liquidacion(jean)
    assert r["valor_empresa"] == pytest.approx(33_333.33, abs=0.01)
    assert r["valor_eps"] == pytest.approx(1_732_666.67, abs=0.02)
    assert r["total_trabajador"] == pytest.approx(1_766_000, abs=0.05)
    assert r["dias_tramite_colaborador"] == 77


def test_reporte_mensual_aparece_cuando_pasa_cada_hito(jean):
    assert monitoreo.reporte_mensual(2026, 11) == []                      # en noviembre lleva solo 30 días
    esperado = {(2027, 2): (120, 90), (2027, 3): (151, 150), (2027, 4): (181, 180), (2027, 7): (257, 180)}
    for (anio, mes), (dias, hito) in esperado.items():
        fila = monitoreo.reporte_mensual(anio, mes)[0]
        assert (fila["dias_acumulados"], fila["hito_superado"]) == (dias, hito), (anio, mes)
    assert monitoreo.reporte_mensual(2027, 8) == []                       # ya terminó


def test_casos_del_mes_explica_cuando_superara_el_siguiente_hito(jean):
    fila = monitoreo.casos_del_mes(2026, 11)[0]
    assert fila["dias_al_cierre"] == 30 and fila["proximo_hito"] == 90 and fila["supera_el"] == "2027-01-30"
    assert monitoreo.casos_del_mes(2027, 4)[0]["proximo_hito"] == "—"      # ya pasó el 180
    # una incapacidad corta nunca alcanza el primer hito
    cid = recepcion.registrar_colaborador("2", "ana", ibc=1)
    recepcion.registrar_incapacidad(cid, rd.TIPO_ENFERMEDAD_GENERAL, "Nueva EPS", date(2026, 11, 2), date(2026, 11, 5),
                                    "Recepción", "r", True, True, [rd.DOC_CERTIFICADO, rd.DOC_EPICRISIS])
    corta = next(f for f in monitoreo.casos_del_mes(2026, 11) if f["colaborador"] == "ana")
    assert corta["supera_el"].startswith("No lo alcanza")


def _pagina(modulo, args=()):
    def script(modulo):
        import importlib

        from core import database
        from core.seguridad import Sesion
        database.init_db()
        importlib.import_module(f"modulos.{modulo}.interfaz").render(Sesion("aux", "Auxiliar de administración de personal"))
    at = AppTest.from_function(script, args=(modulo,), default_timeout=30)
    at.run()
    return at


def test_pantalla_liquidacion_muestra_el_total_al_trabajador(jean):
    at = _pagina("liquidacion")
    assert not at.exception, at.exception
    metricas = {}
    for m in at.metric:                      # la calculadora repite etiquetas: vale la primera (pestaña «Por incapacidad»)
        metricas.setdefault(m.label, m.value)
    assert metricas["Total a pagar al trabajador (días 1 a 180)"] == "$1.766.000"
    assert metricas["Lo asume la empresa"] == "$33.333" and metricas["Lo debe reconocer la EPS"] == "$1.732.667"
    assert metricas["Días sin pago por nómina (181+)"] == "77"
    assert any("Conciliación" in i.value and "NO se le paga" in i.value for i in at.info)


def test_pantalla_monitoreo_explica_el_caso_en_el_mes_de_inicio(jean):
    def script():
        from datetime import date
        from core import database
        from core.seguridad import Sesion
        from modulos.monitoreo import interfaz
        database.init_db()
        interfaz.render(Sesion("aux", "Auxiliar de administración de personal"))
    at = AppTest.from_function(script, default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    at.number_input(key="mon_anio").set_value(2026).run()
    at.selectbox(key="mon_mes").select(11).run()
    assert not at.exception, at.exception
    assert any("Ningún caso supera 90 días" in i.value for i in at.info)
    assert any(e.label.startswith("Ver todos los casos") and e.proto.expanded for e in at.expander)
