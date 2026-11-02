"""Conciliación sin valor calculado, edición de colaborador y envío de correo."""
import smtplib
import sqlite3
from datetime import date, timedelta

import pytest
from streamlit.testing.v1 import AppTest

from config import estados, settings, reglas_documentos as rd
from core import consultas, database, notificaciones, seguridad
from modulos.ausentismo import servicio as ausentismo
from modulos.conciliacion import servicio as conciliacion
from modulos.recepcion import servicio as recepcion
from modulos.seguimiento_cobro import servicio as cobro
from modulos.transcripcion import servicio as transcripcion
from modulos.verificacion import servicio as verificacion

HOY = date.today()


def _incapacidad(ibc, dias=10, entidad="Salud Total", hasta=estados.TRANSCRITA):
    cid = recepcion.registrar_colaborador(f"D{ibc}{dias}{entidad}", "Persona", "C", "A", "lider1", "p@x.co", ibc)
    ini = HOY - timedelta(days=dias + 1)
    docs = rd.documentos_requeridos(rd.TIPO_ENFERMEDAD_GENERAL, dias)
    inc = recepcion.registrar_incapacidad(cid, rd.TIPO_ENFERMEDAD_GENERAL, entidad, ini,
                                          ini + timedelta(days=dias - 1), "Recepción", "r", True, True, docs)
    if hasta == estados.RECIBIDA:
        return inc
    verificacion.verificar(inc, docs, True)
    if hasta == estados.VERIFICADA:
        return inc
    transcripcion.registrar_transcripcion(inc, HOY, "Portal de la entidad", "R")
    return inc


# ------------------------------------------------------------------ el caso de la captura (IBC en 0)
def test_pago_se_puede_asignar_aunque_el_ibc_sea_cero():
    inc = _incapacidad(ibc=0)
    pago = conciliacion.registrar_pago("Salud Total", HOY, 30_000, "C-1")
    sug = conciliacion.sugerencias(pago)
    assert [s["id"] for s in sug] == [inc]
    assert sug[0]["esperado"] is None and "IBC" in sug[0]["motivo"]
    conciliacion.aplicar_pago(pago, inc, 30_000, dias_pagados=3)
    assert conciliacion.pagos_pendientes() == []
    fila = conciliacion.saldos_por_entidad()[0]
    assert (fila["incapacidades"], fila["sin_valor"], fila["esperado"], fila["pagado"]) == (1, 1, 0.0, 30_000)
    df = conciliacion.reporte_mensual(HOY.year, HOY.month)
    assert df.iloc[0]["Días pagados"] == 3 and df.iloc[0]["Días de la incapacidad"] == 10


def test_motivos_sin_valor():
    corta = consultas.obtener_incapacidad(_incapacidad(ibc=2_000_000, dias=2))
    assert "2 días o menos" in conciliacion.motivo_sin_valor(corta)
    normal = consultas.obtener_incapacidad(_incapacidad(ibc=2_000_000, dias=10, entidad="Nueva EPS"))
    assert conciliacion.motivo_sin_valor(normal) is None


def test_diagnostico_cuando_no_hay_candidatas():
    assert "ninguna incapacidad" in conciliacion.diagnostico_entidad("Salud Total")[0]
    _incapacidad(ibc=1_000_000, hasta=estados.VERIFICADA)
    assert "Verificada" in conciliacion.diagnostico_entidad("Salud Total")[0]
    pago = conciliacion.registrar_pago("Salud Total", HOY, 1000)
    assert conciliacion.sugerencias(pago) == []


def test_dias_pagados_validados():
    inc = _incapacidad(ibc=1_000_000, dias=5)
    pago = conciliacion.registrar_pago("Salud Total", HOY, 50_000)
    with pytest.raises(ValueError):
        conciliacion.aplicar_pago(pago, inc, 10_000, dias_pagados=6)
    conciliacion.aplicar_pago(pago, inc, 10_000, dias_pagados=5)


def test_migracion_agrega_columna_a_bases_antiguas(entorno):
    database.init_db()
    con = sqlite3.connect(settings.DB_PATH)
    con.execute("ALTER TABLE pagos_aplicaciones RENAME TO tmp")
    con.execute("CREATE TABLE pagos_aplicaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, pago_id INTEGER, "
                "incapacidad_id INTEGER, valor REAL, usuario TEXT, creado_en TEXT)")
    con.execute("DROP TABLE tmp")
    con.commit()
    con.close()
    database.init_db()
    columnas = {r["name"] for r in database.fetch_all("PRAGMA table_info(pagos_aplicaciones)")}
    assert "dias_pagados" in columnas


def test_editar_colaborador_corrige_el_ibc():
    cid = recepcion.registrar_colaborador("1", "Ana", ibc=0)
    recepcion.actualizar_colaborador(cid, ibc=3_000_000, area="Ventas")
    c = consultas.obtener_colaborador(cid)
    assert c["ibc"] == 3_000_000 and c["area"] == "Ventas" and c["nombre"] == "Ana"
    with pytest.raises(ValueError):
        recepcion.actualizar_colaborador(cid, ibc=-1)
    with pytest.raises(ValueError):
        recepcion.actualizar_colaborador(cid, nombre=" ")
    with pytest.raises(ValueError):
        recepcion.actualizar_colaborador(999, ibc=1)


# ------------------------------------------------------------------ correo (con servidor simulado)
class FakeSMTP:
    enviados: list = []
    login_args = None
    error_login = None
    error_conexion = None

    def __init__(self, host, port, timeout=None):
        if FakeSMTP.error_conexion:
            raise FakeSMTP.error_conexion
        FakeSMTP.host, FakeSMTP.port = host, port

    def login(self, usuario, clave):
        if FakeSMTP.error_login:
            raise FakeSMTP.error_login
        FakeSMTP.login_args = (usuario, clave)

    def send_message(self, msg):
        FakeSMTP.enviados.append(msg)

    def starttls(self):
        pass

    def quit(self):
        pass


@pytest.fixture
def smtp(monkeypatch, entorno):
    FakeSMTP.enviados, FakeSMTP.login_args, FakeSMTP.error_login, FakeSMTP.error_conexion = [], None, None, None
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    settings.ENV_FILE.write_text("# cuenta\nSMTP_USER=soyvato91@gmail.com\nSMTP_PASSWORD=abcd efgh ijkl mnop\n",
                                 encoding="utf-8")
    return FakeSMTP


def test_validar_correos():
    assert notificaciones.validar_correos("Pedro@Gmail.com, ana@x.co; pedro@gmail.com") == ["pedro@gmail.com", "ana@x.co"]
    for malo in ("", "pedro@gmail", "pedro gmail.com", "a@b.co, malo"):
        with pytest.raises(ValueError):
            notificaciones.validar_correos(malo)
    with pytest.raises(ValueError):
        notificaciones.validar_correos(",".join(f"u{i}@x.co" for i in range(11)))


def test_configuracion_desde_archivo_env(smtp):
    cfg = notificaciones.configuracion_smtp()
    assert cfg["usuario"] == "soyvato91@gmail.com" and cfg["clave"] == "abcdefghijklmnop"   # sin espacios
    assert (cfg["host"], cfg["port"], cfg["remitente"]) == ("smtp.gmail.com", 465, "soyvato91@gmail.com")
    settings.ENV_FILE.write_text("SMTP_USER=a@b.co\n", encoding="utf-8")                  # falta la contraseña
    assert notificaciones.smtp_configurado() is False


def test_sin_configurar_explica_que_hacer(entorno):
    with pytest.raises(notificaciones.CorreoError, match=".env"):
        notificaciones.enviar_correo(["a@b.co"], "x", "y")


def test_enviar_reporte_de_ausentismo_con_excel_adjunto(smtp):
    cid = recepcion.registrar_colaborador("1", "Ana", area="Ventas")
    recepcion.registrar_incapacidad(cid, rd.TIPO_ENFERMEDAD_GENERAL, "Nueva EPS", date(2026, 2, 1), date(2026, 2, 3),
                                    "Recepción", "r", True, True, [rd.DOC_CERTIFICADO, rd.DOC_EPICRISIS])
    ruta, correos = ausentismo.enviar_por_correo(2026, 2, "pedro@gmail.com", "tester")
    assert correos == ["pedro@gmail.com"] and smtp.login_args == ("soyvato91@gmail.com", "abcdefghijklmnop")
    msg = smtp.enviados[0]
    assert msg["To"] == "pedro@gmail.com" and msg["From"] == "soyvato91@gmail.com"
    assert "2026-02" in msg["Subject"]
    adjuntos = list(msg.iter_attachments())
    assert adjuntos[0].get_filename() == "ausentismo_2026-02.xlsx" and len(adjuntos[0].get_content()) > 1000
    assert "confidencial" in msg.get_body().get_content()
    registro = notificaciones.listar()[0]
    assert registro["estado"] == "Enviada" and registro["categoria"] == "Ausentismo"
    assert notificaciones.ultimos_destinatarios() == "pedro@gmail.com"
    # se puede reenviar el mismo mes (a otra persona) sin error
    ausentismo.enviar_por_correo(2026, 2, "ana@x.co", "tester")
    assert len(smtp.enviados) == 2
    with pytest.raises(ValueError):
        ausentismo.enviar_por_correo(2026, 2, "no-es-correo", "tester")
    assert len(smtp.enviados) == 2


def test_errores_de_correo_son_claros(smtp):
    smtp.error_login = smtplib.SMTPAuthenticationError(535, b"bad")
    with pytest.raises(notificaciones.CorreoError, match="contraseña de aplicación"):
        notificaciones.enviar_correo(["a@b.co"], "x", "y")
    smtp.error_login, smtp.error_conexion = None, OSError("sin red")
    with pytest.raises(notificaciones.CorreoError, match="conexión"):
        notificaciones.enviar_correo(["a@b.co"], "x", "y")


def test_si_falla_el_envio_no_queda_registrado_como_enviado(smtp):
    smtp.error_login = smtplib.SMTPAuthenticationError(535, b"bad")
    with pytest.raises(notificaciones.CorreoError):
        ausentismo.enviar_por_correo(2026, 2, "pedro@gmail.com", "tester")
    assert notificaciones.listar() == [] and ausentismo.repo.reporte_enviado("2026-02") is None


def test_enviar_pendientes_de_la_bandeja(smtp):
    notificaciones.crear("Prueba", "Colaborador", "Ana", "Asunto 1", "Mensaje 1", correo="ana@x.co")
    notificaciones.crear("Prueba", "Jefe", "Luis", "Sin correo", "Mensaje 2")
    r = notificaciones.enviar_pendientes()
    assert r == {"enviadas": 1, "errores": 0, "motivo": ""}
    estados_ = {n["asunto"]: n["estado"] for n in notificaciones.listar()}
    assert estados_ == {"Asunto 1": "Enviada", "Sin correo": "Pendiente"}


def test_pantalla_ausentismo_envia_el_correo(smtp):
    def script():
        from core import database
        from core.seguridad import Sesion
        from modulos.ausentismo import interfaz
        database.init_db()
        interfaz.render(Sesion("aux", "Auxiliar de administración de personal"))
    at = AppTest.from_function(script, default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    at.text_input(key="aus_dest").set_value("pedro@gmail.com").run()
    at.button(key="aus_enviar").click().run()
    assert not at.exception, at.exception
    assert smtp.enviados and smtp.enviados[0]["To"] == "pedro@gmail.com"
    at.text_input(key="aus_dest").set_value("malo").run()
    at.button(key="aus_enviar").click().run()
    assert any("no válido" in e.value for e in at.error)


def test_pantalla_conciliacion_con_el_caso_de_ibc_cero():
    inc = _incapacidad(ibc=0)
    pago = conciliacion.registrar_pago("Salud Total", HOY, 30_000, "C-1")

    def script():
        from core import database
        from core.seguridad import Sesion
        from modulos.conciliacion import interfaz
        database.init_db()
        interfaz.render(Sesion("aux", "Auxiliar de administración de personal"))
    at = AppTest.from_function(script, default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    assert any("no tiene valor calculado" in i.value for i in at.info)       # explica por qué
    at.button(key="con_aplicar_btn").click().run()                            # y deja asignar igual
    assert not at.exception, at.exception
    assert conciliacion.pagos_pendientes() == [] and consultas.pagado_a_incapacidad(inc) == 30_000
