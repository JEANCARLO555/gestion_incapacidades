"""Reglas del negocio: documentos, pagos, plazos y días hábiles."""
from datetime import date

import pytest

from config import estados, plazos_eps, reglas_documentos as rd, reglas_monitoreo as rm, reglas_pago as rp
from core import utils


def test_epicrisis_solo_si_enfermedad_general_supera_2_dias():
    assert rd.documentos_requeridos(rd.TIPO_ENFERMEDAD_GENERAL, 2) == [rd.DOC_CERTIFICADO]
    assert rd.DOC_EPICRISIS in rd.documentos_requeridos(rd.TIPO_ENFERMEDAD_GENERAL, 3)


def test_documentos_por_tipo():
    assert rd.DOC_FURIPS in rd.documentos_requeridos(rd.TIPO_ACCIDENTE_TRANSITO, 1)
    assert rd.DOC_EPICRISIS in rd.documentos_requeridos(rd.TIPO_ACCIDENTE_LABORAL, 1)
    mat = rd.documentos_requeridos(rd.TIPO_LICENCIA_MATERNIDAD, 126)
    assert rd.DOC_REGISTRO_CIVIL in mat and rd.DOC_IDENTIDAD in mat
    pat = rd.documentos_requeridos(rd.TIPO_LICENCIA_PATERNIDAD, 14)
    assert rd.DOC_IDENTIDAD_MADRE in pat and rd.DOC_CERTIFICADO not in pat
    with pytest.raises(ValueError):
        rd.documentos_requeridos("otro", 1)


def test_tramos_de_pago():
    assert rp.tramo_para_dia(1).responsable == rp.EMPRESA
    assert rp.tramo_para_dia(2).porcentaje == 1.0
    assert (rp.tramo_para_dia(3).responsable, rp.tramo_para_dia(3).porcentaje) == (rp.EPS, 0.67)
    assert rp.tramo_para_dia(90).porcentaje == 0.67
    assert rp.tramo_para_dia(91).porcentaje == 0.50
    assert rp.tramo_para_dia(180).porcentaje == 0.50
    assert rp.tramo_para_dia(181).responsable == rp.TRAMITE_COLABORADOR


def test_liquidar_100_dias_ibc_3_millones():
    filas = rp.liquidar_dias(3_000_000, 0, 100)
    empresa = sum(f["valor"] for f in filas if f["responsable"] == rp.EMPRESA)
    eps = sum(f["valor"] for f in filas if f["responsable"] == rp.EPS)
    assert empresa == 200_000                     # 2 días x 100.000
    assert eps == 88 * 67_000 + 10 * 50_000       # días 3-90 y 91-100
    # con días previos los tramos se desplazan
    assert rp.liquidar_dias(3_000_000, 89, 2)[1]["porcentaje"] == 0.50


def test_plazos_eps():
    assert plazos_eps.fecha_limite_transcripcion("Nueva EPS", rd.TIPO_ENFERMEDAD_GENERAL, "2026-01-31") == date(2027, 1, 31)
    assert plazos_eps.fecha_limite_transcripcion("Salud Total", rd.TIPO_ACCIDENTE_TRANSITO, "2026-01-01") == date(2026, 1, 16)
    assert plazos_eps.fecha_limite_transcripcion("SURA EPS", rd.TIPO_ENFERMEDAD_GENERAL, "2026-01-01") == date(2026, 5, 31)
    assert plazos_eps.fecha_limite_transcripcion("Sanitas", rd.TIPO_ENFERMEDAD_GENERAL, "2026-01-01") == date(2029, 1, 1)
    assert plazos_eps.fecha_limite_transcripcion("Famisanar", rd.TIPO_ENFERMEDAD_GENERAL, "2026-01-01") is None
    # paternidad: 30 días desde el nacimiento, sin importar la EPS
    assert plazos_eps.fecha_limite_transcripcion("Nueva EPS", rd.TIPO_LICENCIA_PATERNIDAD, "2026-03-01", "2026-02-20") == date(2026, 3, 22)


def test_utils_fechas():
    assert utils.dias_inclusivos("2026-01-01", "2026-01-03") == 3
    assert utils.sumar_meses("2026-01-31", 1) == date(2026, 2, 28)
    # viernes + 3 días hábiles = miércoles (2026-03-06 es viernes; lunes 9 festivo en CO -> evitar)
    assert utils.sumar_dias_habiles("2026-02-06", 3) == date(2026, 2, 11)
    assert utils.es_dia_habil("2026-02-07") is False   # sábado
    assert utils.nombre_seguro("Ana Pérez/ñandú") == "Ana_Perez_nandu"


def test_estados_y_hitos():
    assert estados.puede_pasar(estados.TRANSCRITA, estados.COBRADA)
    assert not estados.puede_pasar(estados.RECIBIDA, estados.PAGADA)
    assert rm.HITOS == (90, 120, 150, 180)
