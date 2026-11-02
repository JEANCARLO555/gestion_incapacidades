"""Pruebas de los módulos, siguiendo el recorrido de una incapacidad."""
from datetime import date, timedelta

import pandas as pd
import pytest

from config import estados, reglas_documentos as rd
from core import consultas, flujo, notificaciones, seguridad
from modulos.archivo import servicio as archivo
from modulos.ausentismo import servicio as ausentismo
from modulos.cartera import servicio as cartera
from modulos.conciliacion import servicio as conciliacion
from modulos.ia import servicio as ia
from modulos.juridico import servicio as juridico
from modulos.monitoreo import servicio as monitoreo
from modulos.nomina import servicio as nomina
from modulos.recepcion import servicio as recepcion
from modulos.seguimiento_cobro import servicio as cobro
from modulos.transcripcion import servicio as transcripcion
from modulos.verificacion import servicio as verificacion
from tests import datos_demo

HOY = date.today()


def _colab(ibc=3_000_000, doc="1", jefe="lider1"):
    return recepcion.registrar_colaborador(doc, f"Persona {doc}", "Cargo", "Comercial", jefe, "p@x.co", ibc)


def _inc(cid, dias=10, entidad="Nueva EPS", tipo=rd.TIPO_ENFERMEDAD_GENERAL, docs=None, fisica=True, **kw):
    ini = kw.pop("ini", HOY - timedelta(days=dias + 1))
    fin = ini + timedelta(days=dias - 1)
    docs = rd.documentos_requeridos(tipo, dias) if docs is None else docs
    return recepcion.registrar_incapacidad(cid, tipo, entidad, ini, fin, "Recepción", "Rec", True,
                                           fisica, docs, **kw)


def _hasta(inc, estado_final):
    """Lleva la incapacidad hasta un estado, por el camino normal."""
    verificacion.verificar(inc, [d["documento"] for d in consultas.documentos_de(inc)], True)
    if estado_final == estados.VERIFICADA:
        return
    transcripcion.registrar_transcripcion(inc, HOY - timedelta(days=200), "Portal de la entidad", "R")
    if estado_final == estados.TRANSCRITA:
        return
    cobro.marcar_cobrada(inc, HOY - timedelta(days=5), fecha_cobro=HOY - timedelta(days=200))


# ------------------------------------------------------------------ recepción
def test_colaborador_duplicado_y_validaciones():
    _colab()
    with pytest.raises(ValueError):
        _colab()
    with pytest.raises(ValueError):
        recepcion.registrar_colaborador("", "x")


def test_recepcion_registra_y_notifica():
    cid = _colab()
    inc = _inc(cid, dias=3)
    fila = consultas.obtener_incapacidad(inc)
    assert fila["estado"] == estados.RECIBIDA and fila["dias"] == 3
    docs = {d["documento"]: d["recibido"] for d in consultas.documentos_de(inc)}
    assert set(docs) == {rd.DOC_CERTIFICADO, rd.DOC_EPICRISIS} and all(docs.values())
    assert {n["destinatario_tipo"] for n in notificaciones.listar()} == {"Jefe inmediato", "Administración de personal"}


def test_recepcion_validaciones():
    cid = _colab()
    with pytest.raises(ValueError):
        recepcion.registrar_incapacidad(cid, rd.TIPO_ACCIDENTE_LABORAL, "Nueva EPS", HOY, HOY - timedelta(days=1),
                                        "Recepción", "x", True, True, [])
    with pytest.raises(ValueError):
        recepcion.registrar_incapacidad(cid, "Inventado", "Nueva EPS", HOY, HOY, "Recepción", "x", True, True, [])
    with pytest.raises(ValueError):
        recepcion.registrar_incapacidad(cid, rd.TIPO_ACCIDENTE_LABORAL, "Nueva EPS", HOY, HOY, "Telepatía", "x", True, True, [])


def test_prorroga_y_advertencias():
    cid = _colab()
    a = _inc(cid, dias=10, ini=HOY - timedelta(days=30))
    b = _inc(cid, dias=5, ini=HOY - timedelta(days=20), prorroga_de=a)
    assert consultas.caso_id_de(b) == a and consultas.dias_previos(b) == 10
    with pytest.raises(ValueError):   # ya tiene prórroga
        _inc(cid, dias=2, prorroga_de=a)
    av = recepcion.advertencias("Correo electrónico", False, False, HOY - timedelta(days=5), HOY)
    assert len(av) == 3


def test_lider_solo_ve_a_su_gente():
    a, b = _colab(doc="1", jefe="lider1"), _colab(doc="2", jefe="lider2")
    _inc(a)
    _inc(b)
    filas = recepcion.listar(seguridad.Sesion("lider1", seguridad.ROL_LIDER))
    assert len(filas) == 1 and filas[0]["jefe_inmediato"] == "lider1"
    assert len(recepcion.listar(seguridad.Sesion("aux", seguridad.ROL_AUXILIAR))) == 2
    # no importan mayúsculas ni espacios de más
    assert len(recepcion.listar(seguridad.Sesion("  LIDER1 ", seguridad.ROL_LIDER))) == 1
    assert recepcion.listar(seguridad.Sesion("usuario", seguridad.ROL_LIDER)) == []


# ------------------------------------------------------------------ verificación
def test_verificacion_incompleta_llamados_y_completa():
    cid = _colab()
    inc = _inc(cid, dias=5, docs=[rd.DOC_CERTIFICADO], fisica=False)
    r = verificacion.verificar(inc, [rd.DOC_CERTIFICADO], False, hoy=date(2026, 2, 6))
    assert r["completa"] is False and r["llamado"] == 1
    assert "epicrisis" in " ".join(r["faltantes"]).lower() and r["fecha_limite"] == date(2026, 2, 11)
    assert consultas.obtener_incapacidad(inc)["estado"] == estados.INCOMPLETA
    with pytest.raises(flujo.FlujoError):     # aún no vence el plazo
        verificacion.registrar_segundo_llamado(inc, hoy=date(2026, 2, 10))
    # repetir la verificación no duplica el primer aviso
    assert verificacion.verificar(inc, [rd.DOC_CERTIFICADO], False, hoy=date(2026, 2, 7))["llamado"] is None
    assert verificacion.estado_llamados(inc, date(2026, 2, 12))["requiere_segundo_llamado"] is True
    verificacion.registrar_segundo_llamado(inc, hoy=date(2026, 2, 12))
    assert verificacion.estado_llamados(inc)["cantidad"] == 2
    with pytest.raises(flujo.FlujoError):
        verificacion.registrar_segundo_llamado(inc, hoy=date(2026, 2, 13))
    avisos = [n for n in notificaciones.listar() if n["categoria"] == "Documentación"]
    assert len(avisos) == 2 and "citado" in avisos[0]["mensaje"]
    r = verificacion.verificar(inc, [rd.DOC_CERTIFICADO, rd.DOC_EPICRISIS], True)
    assert r["completa"] and consultas.obtener_incapacidad(inc)["estado"] == estados.VERIFICADA


def test_archivo_digital_organizado_y_clinico(entorno):
    cid = _colab()
    inc = _inc(cid, dias=5)
    ruta = verificacion.guardar_archivo_digital(inc, rd.DOC_EPICRISIS, "scan 1.pdf", b"%PDF")
    ruta2 = verificacion.guardar_archivo_digital(inc, rd.DOC_EPICRISIS, "scan 1.pdf", b"%PDF")
    assert ruta != ruta2 and "Nueva_EPS" in ruta and "Persona_1_" in ruta
    assert all(a["es_clinico"] for a in verificacion.archivos_de(inc))
    with pytest.raises(ValueError):
        verificacion.guardar_archivo_digital(inc, rd.DOC_CERTIFICADO, "x.pdf", b"")


# ------------------------------------------------------------------ transcripción
def test_transcripcion_plazos_y_medios():
    cid = _colab()
    inc = _inc(cid, dias=3, entidad="SOS")
    with pytest.raises(flujo.FlujoError):        # aún sin verificar
        transcripcion.registrar_transcripcion(inc, HOY, "Correo electrónico", "x")
    verificacion.verificar(inc, [d["documento"] for d in consultas.documentos_de(inc)], True)
    assert transcripcion.por_transcribir()[0]["manual"] is True
    with pytest.raises(ValueError):              # SOS no permite portal
        transcripcion.registrar_transcripcion(inc, HOY, "Portal de la entidad", "x")
    r = transcripcion.registrar_transcripcion(inc, HOY, "Correo electrónico", "RAD1")
    assert r["fuera_de_plazo"] is False
    assert consultas.obtener_incapacidad(inc)["estado"] == estados.TRANSCRITA


def test_transcripcion_fuera_de_plazo_y_orden():
    cid = _colab()
    vieja = _inc(cid, dias=3, entidad="SURA EPS", ini=HOY - timedelta(days=200))
    nueva = _inc(cid, dias=3, entidad="Nueva EPS", ini=HOY - timedelta(days=2))
    for i in (vieja, nueva):
        verificacion.verificar(i, [d["documento"] for d in consultas.documentos_de(i)], True)
    assert [f["id"] for f in transcripcion.por_transcribir()][0] == vieja      # la más urgente primero
    assert transcripcion.por_transcribir()[0]["vencido"] is True
    assert transcripcion.registrar_transcripcion(vieja, HOY, "Portal de la entidad", "R")["fuera_de_plazo"] is True


# ------------------------------------------------------------------ seguimiento
def test_rechazo_improcedente_vs_subsanable():
    cid = _colab()
    a, b = _inc(cid, ini=HOY - timedelta(days=40)), _inc(cid, ini=HOY - timedelta(days=20))
    for i in (a, b):
        _hasta(i, estados.TRANSCRITA)
    cobro.marcar_rechazada(a, "Falta firma", False)
    cobro.marcar_rechazada(b, "Causal inexistente", True)
    assert [f["id"] for f in transcripcion.por_transcribir()] == []        # aún sin subsanar
    cobro.subsanar_rechazo(a)
    assert [f["id"] for f in transcripcion.por_transcribir()] == [a]
    with pytest.raises(flujo.FlujoError):
        cobro.subsanar_rechazo(b)                                             # improcedente: va a jurídico
    transcripcion.registrar_transcripcion(a, HOY, "Portal de la entidad", "R2")
    assert consultas.obtener_incapacidad(a)["estado"] == estados.TRANSCRITA
    with pytest.raises(ValueError):
        cobro.marcar_rechazada(a, " ", False)


def test_seguimiento_semanal():
    cid = _colab()
    inc = _inc(cid)
    _hasta(inc, estados.TRANSCRITA)
    assert cobro.pendientes_seguimiento()[0]["ultimo_seguimiento"] == "Nunca"
    cobro.registrar_seguimiento(inc, "Se consultó el portal")
    assert cobro.pendientes_seguimiento() == []
    assert cobro.pendientes_seguimiento(HOY + timedelta(days=8))
    with pytest.raises(ValueError):
        cobro.registrar_seguimiento(inc, " ")


# ------------------------------------------------------------------ cartera y jurídico
def test_cartera_reglas_de_traslado_y_escalamiento():
    cid = _colab()
    inc = _inc(cid)
    _hasta(inc, estados.COBRADA)                       # cobrada hace 200 días
    with pytest.raises(flujo.FlujoError, match="requerimientos"):
        cartera.trasladar_a_cartera(inc)
    texto = cartera.generar_requerimiento(inc)
    assert "No. 1" in texto and "Persona 1" in texto and "$" in texto
    cartera.registrar_requerimiento(inc, "Llamada a la EPS")
    cartera.registrar_acuerdo_pago(inc, HOY + timedelta(days=20), "Acordaron pagar")
    assert consultas.obtener_incapacidad(inc)["fecha_promesa_pago"] == (HOY + timedelta(days=20)).isoformat()
    cartera.trasladar_a_cartera(inc)
    assert consultas.obtener_incapacidad(inc)["estado"] == estados.EN_CARTERA
    with pytest.raises(flujo.FlujoError):              # cartera debe gestionar primero
        cartera.escalar_a_juridico(inc)
    cartera.registrar_gestion_cartera(inc, "Carta a la gerencia de la EPS")
    cartera.escalar_a_juridico(inc)
    assert consultas.obtener_incapacidad(inc)["estado"] == estados.EN_JURIDICO


def test_cartera_traslado_por_deterioro_y_forzado():
    cid = _colab()
    inc = _inc(cid)
    _hasta(inc, estados.TRANSCRITA)
    cobro.marcar_cobrada(inc, HOY, fecha_cobro=HOY - timedelta(days=10))
    cartera.generar_requerimiento(inc)
    cartera.registrar_requerimiento(inc, "segundo")
    with pytest.raises(flujo.FlujoError, match="180"):
        cartera.trasladar_a_cartera(inc)
    cartera.marcar_deterioro_crediticio(inc, "La EPS entró en liquidación")
    cartera.trasladar_a_cartera(inc)
    assert consultas.obtener_incapacidad(inc)["estado"] == estados.EN_CARTERA
    otra = _inc(cid, ini=HOY - timedelta(days=60))
    _hasta(otra, estados.COBRADA)
    with pytest.raises(ValueError):
        cartera.trasladar_a_cartera(otra, forzar=True)
    cartera.trasladar_a_cartera(otra, forzar=True, justificacion="Instrucción de gerencia")


def test_alerta_de_prescripcion_3_anios():
    cid = _colab()
    inc = _inc(cid)
    verificacion.verificar(inc, [d["documento"] for d in consultas.documentos_de(inc)], True)
    transcripcion.registrar_transcripcion(inc, HOY - timedelta(days=3 * 365 - 30), "Portal de la entidad", "R")
    cobro.marcar_cobrada(inc, HOY - timedelta(days=1))
    fila = cartera.candidatas()[0]
    assert fila["riesgo_prescripcion"] is True and fila["en_mora"] is True


def test_juridico_derecho_de_peticion_tutela_y_decision():
    cid = _colab()
    inc = _inc(cid)
    _hasta(inc, estados.COBRADA)                               # promesa vencida hace 5 días
    assert juridico.elegibles()[0]["motivo"].startswith("Incumplió")
    juridico.abrir_caso(inc)
    with pytest.raises(flujo.FlujoError):                      # sin derecho de petición no hay tutela
        juridico.radicar_tutela(inc, HOY, "T1")
    texto = juridico.radicar_derecho_peticion(inc, HOY - timedelta(days=30), "DP1")
    assert "Derecho de petición" in texto
    assert juridico.estado_peticion(inc)["vencida"] is True
    juridico.radicar_tutela(inc, HOY, "T1")
    with pytest.raises(ValueError):
        juridico.decidir(inc, "Dar de baja", "")
    juridico.decidir(inc, "Dar de baja", "Entidad liquidada")
    assert consultas.obtener_incapacidad(inc)["estado"] == estados.DADA_DE_BAJA


def test_juridico_rechazo_improcedente_y_termino():
    cid = _colab()
    inc = _inc(cid)
    _hasta(inc, estados.TRANSCRITA)
    with pytest.raises(flujo.FlujoError):
        juridico.abrir_caso(inc)
    cobro.marcar_rechazada(inc, "Causal que no aplica", True)
    juridico.abrir_caso(inc)
    juridico.radicar_derecho_peticion(inc, HOY, "DP")
    with pytest.raises(flujo.FlujoError, match="término"):
        juridico.radicar_tutela(inc, HOY, "T")
    gestion = juridico._peticiones_sin_respuesta(inc)[0]["id"]
    juridico.registrar_respuesta(gestion)
    assert juridico.estado_peticion(inc)["hay_pendiente"] is False


# ------------------------------------------------------------------ liquidación
def test_liquidacion_con_prorroga_y_sin_regla():
    cid = _colab(ibc=3_000_000)
    a = _inc(cid, dias=89, ini=HOY - timedelta(days=200))
    b = _inc(cid, dias=3, ini=HOY - timedelta(days=100), prorroga_de=a)
    r = consultas.resumen_liquidacion(b)
    assert r["dias_previos"] == 89
    assert [t["porcentaje"] for t in r["tramos"]] == [0.67, 0.5] and r["valor_empresa"] == 0
    assert r["valor_eps"] == 67_000 + 2 * 50_000
    lab = _inc(cid, dias=4, tipo=rd.TIPO_ACCIDENTE_LABORAL)
    assert consultas.resumen_liquidacion(lab)["aplica"] is False
    assert consultas.liquidacion_diaria(lab) == []


# ------------------------------------------------------------------ monitoreo
def test_hitos_y_reporte_mensual():
    cid = _colab()
    a = _inc(cid, dias=90, ini=HOY - timedelta(days=130))
    b = _inc(cid, dias=60, ini=HOY - timedelta(days=40), prorroga_de=a)     # activa: 90 + 41 = 131 hoy
    caso = consultas.caso_id_de(b)
    assert consultas.acumulado_caso_a_fecha(caso, HOY) == 131
    casos = {c["caso_id"]: c for c in monitoreo.hitos.casos_activos()}
    assert casos[caso]["dias"] == 131 and monitoreo.hitos.hito_superado(131) == 120
    assert monitoreo.hitos.hito_superado(90) is None and monitoreo.hitos.hito_superado(181) == 180
    filas = monitoreo.reporte_mensual(HOY.year, HOY.month)
    assert filas and filas[0]["hito_superado"] in (90, 120) and filas[0]["supera_90"] is True


def test_rehabilitacion_flujo_completo():
    cid = _colab()
    a = _inc(cid, dias=100, ini=HOY - timedelta(days=130))
    b = _inc(cid, dias=40, ini=HOY - timedelta(days=30), prorroga_de=a)   # 130 días acumulados hoy
    caso = consultas.caso_id_de(b)
    tarea = monitoreo.tablero_rehabilitacion()[0]
    assert tarea["accion"] == "Notificar que no se expidió" and tarea["urgencia"] == 3
    assert monitoreo.notificar_no_expedido(caso) == 4
    with pytest.raises(ValueError):
        monitoreo.notificar_no_expedido(caso)
    with pytest.raises(ValueError):
        monitoreo.registrar_envio_afp(caso, HOY)                          # aún no hay concepto
    monitoreo.registrar_emision(caso, HOY, "Favorable")
    assert monitoreo.tablero_rehabilitacion()[0]["accion"] == "Enviar concepto a la AFP"
    monitoreo.registrar_envio_afp(caso, HOY)
    monitoreo.comunicar_resultado(caso, HOY)
    assert monitoreo.tablero_rehabilitacion()[0]["accion"] == "Cumplido"
    with pytest.raises(ValueError):
        monitoreo.registrar_emision(caso, HOY, "Quizás")


def test_suspension_y_reintegros():
    cid = _colab()
    a = _inc(cid, dias=200, ini=HOY - timedelta(days=190))                  # activa, 191 días hoy
    caso = consultas.caso_id_de(a)
    assert "suspensión" in monitoreo.tablero_rehabilitacion()[0]["mensaje"]
    monitoreo.comunicar_suspension(caso)
    with pytest.raises(ValueError):
        monitoreo.comunicar_suspension(caso)
    monitoreo.registrar_reintegro(a, HOY, 500_000, "Fondo de pensiones")
    assert monitoreo.listar_reintegros()[0]["valor"] == 500_000
    corta = _inc(cid, dias=10, ini=HOY - timedelta(days=400))
    with pytest.raises(ValueError):
        monitoreo.registrar_reintegro(corta, HOY, 1)


# ------------------------------------------------------------------ conciliación
def test_conciliacion_sugerencias_aplicacion_y_saldos():
    cid = _colab(ibc=3_000_000)
    inc = _inc(cid, dias=10)                      # 2 días empresa + 8 EPS = 8 x 67.000 = 536.000
    otra = _inc(cid, dias=4, ini=HOY - timedelta(days=60))
    for i in (inc, otra):
        _hasta(i, estados.COBRADA)
    pago = conciliacion.registrar_pago("Nueva EPS", HOY, 536_000, "C-1")
    sug = conciliacion.sugerencias(pago)
    assert sug[0]["id"] == inc and sug[0]["coincidencia"] == 1.0
    with pytest.raises(ValueError):
        conciliacion.aplicar_pago(pago, inc, 600_000)                       # más de lo disponible
    conciliacion.aplicar_pago(pago, inc, 500_000)
    assert conciliacion.pagos_pendientes()[0]["sin_identificar"] == 36_000
    conciliacion.aplicar_pago(pago, otra, 36_000)
    assert conciliacion.pagos_pendientes() == []
    saldos = conciliacion.saldos_por_entidad()[0]
    assert saldos["pagado"] == 536_000 and saldos["esperado"] == 536_000 + 2 * 67_000 - 0
    otra_pago = conciliacion.registrar_pago("SURA EPS", HOY, 1000)
    with pytest.raises(ValueError):
        conciliacion.aplicar_pago(otra_pago, inc, 10)                       # entidad distinta
    conciliacion.notificar_pagos_sin_identificar()
    df = conciliacion.reporte_mensual(HOY.year, HOY.month)
    assert not df.empty and df["Valor pagado"].sum() == 536_000
    assert conciliacion.exportar_reporte(HOY.year, HOY.month).endswith(".xlsx")


def test_conciliacion_pagada_sin_pago_registrado():
    cid = _colab()
    inc = _inc(cid)
    _hasta(inc, estados.COBRADA)
    cobro.marcar_pagada(inc)
    assert [f["id"] for f in conciliacion.pagadas_sin_pago_registrado()] == [inc]
    with pytest.raises(ValueError):
        conciliacion.registrar_pago("Nueva EPS", HOY, 0)


# ------------------------------------------------------------------ nómina
def test_nomina_novedades_por_mes():
    cid = _colab(ibc=3_000_000)
    inc = recepcion.registrar_incapacidad(cid, rd.TIPO_ENFERMEDAD_GENERAL, "Nueva EPS", date(2026, 1, 30),
                                          date(2026, 2, 3), "Recepción", "x", True, True,
                                          [rd.DOC_CERTIFICADO, rd.DOC_EPICRISIS])
    lab = _inc(cid, dias=3, tipo=rd.TIPO_ACCIDENTE_LABORAL)
    for i in (inc, lab):
        _hasta(i, estados.TRANSCRITA)
    r = nomina.generar_novedades(2026, 1)
    assert r["generadas"] == 1
    enero = nomina.novedades(2026, 1)[0]
    assert (enero["dias"], enero["dias_empresa"], enero["dias_eps"]) == (2, 2, 0) and enero["valor_empresa"] == 200_000
    nomina.generar_novedades(2026, 2)
    feb = nomina.novedades(2026, 2)[0]
    assert (feb["dias"], feb["dias_eps"], feb["valor_eps"]) == (3, 3, 201_000)
    assert nomina.marcar_reportadas(2026, 2) == 1
    assert nomina.generar_novedades(2026, 2)["ya_reportadas"] == 1
    assert nomina.exportar_csv(2026, 2).endswith(".csv")
    with pytest.raises(ValueError):
        nomina.exportar_csv(2030, 1)


# ------------------------------------------------------------------ ausentismo
def test_ausentismo_indicadores_y_envio():
    c1, c2 = _colab(doc="1"), _colab(doc="2")
    recepcion.registrar_incapacidad(c1, rd.TIPO_ENFERMEDAD_GENERAL, "Nueva EPS", date(2026, 1, 30), date(2026, 2, 3),
                                    "Recepción", "x", True, True, [rd.DOC_CERTIFICADO, rd.DOC_EPICRISIS])
    ind = ausentismo.indicadores(2026, 2)
    assert ind["totales"]["dias_perdidos"] == 3 and ind["totales"]["colaboradores_activos"] == 2
    assert ind["totales"]["indice_ausentismo_pct"] == round(3 / (2 * 28) * 100, 2)
    assert "diagnostico" not in " ".join(ind["detalle"].columns).lower()
    assert ausentismo.plazo_envio(2026, 12) == date(2027, 1, 3)
    ruta = ausentismo.registrar_envio(2026, 2)
    assert ruta.endswith("ausentismo_2026-02.xlsx") and len(pd.read_excel(ruta, sheet_name=None)) == 5
    with pytest.raises(ValueError):
        ausentismo.registrar_envio(2026, 2)
    assert ausentismo.reporte_pendiente(date(2026, 3, 2)) is None
    assert ausentismo.reporte_pendiente(date(2026, 4, 5))["vencido"] is True


# ------------------------------------------------------------------ archivo
def test_archivo_cierre_y_destruccion_de_clinicos():
    cid = _colab()
    inc = _inc(cid)
    ruta = verificacion.guardar_archivo_digital(inc, rd.DOC_EPICRISIS, "epicrisis.pdf", b"%PDF")
    cert = verificacion.guardar_archivo_digital(inc, rd.DOC_CERTIFICADO, "cert.pdf", b"%PDF")
    with pytest.raises(flujo.FlujoError):
        archivo.verificar_contra_pago(inc)                      # aún no está pagada
    _hasta(inc, estados.COBRADA)
    cobro.marcar_pagada(inc)
    archivo.asignar_ubicacion(inc, "Nueva EPS / Caja 1")
    archivo.registrar_soporte_liquidacion(inc)
    with pytest.raises(flujo.FlujoError):
        archivo.enviar_a_gestion_documental(inc)                # falta verificar
    with pytest.raises(flujo.FlujoError, match="Falta"):
        archivo.cerrar(inc)
    archivo.verificar_contra_pago(inc)
    archivo.enviar_a_gestion_documental(inc)
    assert archivo.destruir_clinicos(inc) == 1
    import os
    assert not os.path.exists(ruta) and os.path.exists(cert)    # solo se borra lo clínico
    archivo.cerrar(inc)
    assert consultas.obtener_incapacidad(inc)["estado"] == estados.ARCHIVADA
    assert archivo.listado_fisico()[0]["ubicacion"] == "Nueva EPS / Caja 1"


# ------------------------------------------------------------------ IA / analítica
def test_ia_indicadores_y_anomalias():
    cid = _colab()
    for k in range(3):                                           # 3 incapacidades en menos de 90 días
        _inc(cid, dias=2, ini=HOY - timedelta(days=60 - k * 20))
    ids = [i["id"] for i in consultas.listar_incapacidades()]
    _hasta(ids[0], estados.TRANSCRITA)
    cobro.marcar_rechazada(ids[0], "x", False)
    ind = ia.indicadores_por_entidad()
    assert ind.iloc[0]["incapacidades"] == 3 and ind.iloc[0]["tasa_rechazo_pct"] == 33.3
    assert {a["tipo"] for a in ia.anomalias()} >= {"Incapacidades frecuentes"}
    ctx = ia.contexto_anonimo()
    assert "Persona" not in str(ctx) and ctx["total_incapacidades"] == 3
    assert ia.ausentismo_por_area().iloc[0]["dias"] == 6


def test_ia_sin_clave_no_falla(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert "no está activa" in ia.consultar("¿qué entidad rechaza más?")
    with pytest.raises(ValueError):
        ia.consultar(" ")


def test_datos_demo_cargan_y_son_coherentes():
    ids = datos_demo.cargar()
    assert consultas.obtener_incapacidad(ids["a2"])["estado"] == estados.TRANSCRITA
    assert monitoreo.tablero_rehabilitacion()                    # el caso de 131 días aparece
    assert verificacion.pendientes()                             # el de Carlos espera verificación
