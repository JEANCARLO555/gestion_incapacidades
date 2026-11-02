"""Lista de carpetas con documentos escaneados, rutas relativas y vista del líder."""
import os
import shutil
import sys
from datetime import date, timedelta

import pytest
from streamlit.testing.v1 import AppTest

from config import estados, reglas_documentos as rd, settings
from core import archivos, consultas, database, seguridad
from modulos.archivo import servicio as archivo
from modulos.recepcion import servicio as recepcion
from modulos.verificacion import servicio as verificacion

HOY = date.today()


def _inc(nombre="jean", doc="1", entidad="Salud Total", jefe="lider1"):
    cid = recepcion.registrar_colaborador(doc, nombre, jefe_inmediato=jefe)
    return recepcion.registrar_incapacidad(cid, rd.TIPO_ENFERMEDAD_GENERAL, entidad, HOY - timedelta(days=3),
                                           HOY - timedelta(days=1), "Recepción", "r", True, True,
                                           [rd.DOC_CERTIFICADO, rd.DOC_EPICRISIS])


def test_lista_de_carpetas_y_documentos():
    a, b = _inc("jean", "1"), _inc("ana", "2", "Nueva EPS")
    verificacion.guardar_archivo_digital(a, rd.DOC_CERTIFICADO, "cert.pdf", b"%PDF-1")
    verificacion.guardar_archivo_digital(a, rd.DOC_EPICRISIS, "epi.pdf", b"%PDF-22")
    verificacion.guardar_archivo_digital(b, rd.DOC_CERTIFICADO, "cert.pdf", b"%PDF-3")
    carpetas = archivo.carpetas_escaneadas()
    assert [c["incapacidad_id"] for c in carpetas] == [b, a]                  # la última carga primero
    jean = next(c for c in carpetas if c["incapacidad_id"] == a)
    assert jean["archivos"] == 2 and jean["colaborador"] == "jean"
    assert jean["carpeta"].endswith(f"Salud_Total{os.sep}jean_{HOY - timedelta(days=3)}")
    docs = archivo.documentos_de_incapacidad(a)
    assert len(docs) == 2 and all(d["existe"] for d in docs) and docs[0]["subido_en"]
    assert {d["es_clinico"] for d in docs} == {0, 1}
    assert archivo.leer_archivo(docs[0]["id"]) in (b"%PDF-1", b"%PDF-22")


def test_archivo_borrado_a_mano_se_marca_como_no_encontrado():
    a = _inc()
    ruta = verificacion.guardar_archivo_digital(a, rd.DOC_CERTIFICADO, "cert.pdf", b"x")
    os.remove(ruta)
    doc = archivo.documentos_de_incapacidad(a)[0]
    assert doc["existe"] is False and doc["tamano_kb"] is None
    with pytest.raises(ValueError, match="No se encuentra"):
        archivo.leer_archivo(doc["id"])


def test_la_base_guarda_rutas_relativas_y_sobrevive_a_mover_la_carpeta(entorno, monkeypatch):
    a = _inc()
    verificacion.guardar_archivo_digital(a, rd.DOC_CERTIFICADO, "cert.pdf", b"contenido")
    guardada = database.fetch_one("SELECT ruta FROM archivos_digitales")["ruta"]
    assert not os.path.isabs(guardada) and guardada.startswith("Salud_Total/")
    nueva = entorno / "otro_lugar" / "archivos_digitales"                         # se mueve el proyecto
    nueva.parent.mkdir()
    shutil.move(str(settings.ARCHIVOS_DIR), str(nueva))
    monkeypatch.setattr(settings, "ARCHIVOS_DIR", nueva)
    doc = archivo.documentos_de_incapacidad(a)[0]
    assert doc["existe"] and archivo.leer_archivo(doc["id"]) == b"contenido"


def test_rutas_absolutas_antiguas_se_reconstruyen(entorno):
    a = _inc()
    ruta = verificacion.guardar_archivo_digital(a, rd.DOC_CERTIFICADO, "cert.pdf", b"viejo")
    antigua = "/otro/pc/proyecto/archivos_digitales/" + archivos.a_relativa(ruta)     # como las de la versión anterior
    database.execute("UPDATE archivos_digitales SET ruta = ?", (antigua,))
    doc = archivo.documentos_de_incapacidad(a)[0]
    assert doc["existe"] and archivo.leer_archivo(doc["id"]) == b"viejo"


def test_no_se_lee_ni_se_borra_fuera_de_la_carpeta(entorno):
    a = _inc()
    verificacion.guardar_archivo_digital(a, rd.DOC_EPICRISIS, "epi.pdf", b"x")
    secreto = entorno / "secreto.txt"
    secreto.write_text("no tocar")
    database.execute("UPDATE archivos_digitales SET ruta = ?", (f"../../{secreto.name}",))
    database.execute("UPDATE archivos_digitales SET ruta = ?", (str(secreto),))
    doc = archivo.documentos_de_incapacidad(a)[0]
    assert doc["existe"] is False
    with pytest.raises(ValueError, match="fuera"):
        archivo.leer_archivo(doc["id"])
    inc = consultas.obtener_incapacidad(a)
    database.update("incapacidades", a, {"estado": estados.PAGADA})
    with pytest.raises(ValueError, match="fuera"):
        archivo.destruir_clinicos(a)
    assert secreto.exists()


def test_abrir_carpeta(monkeypatch):
    a = _inc()
    verificacion.guardar_archivo_digital(a, rd.DOC_CERTIFICADO, "cert.pdf", b"x")
    with pytest.raises(ValueError, match="Windows"):
        archivo.abrir_carpeta(a)                                                    # este entorno no es Windows
    abiertas = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(os, "startfile", abiertas.append, raising=False)
    assert archivo.abrir_carpeta(a) == str(abiertas[0])
    with pytest.raises(ValueError, match="no tiene documentos"):
        archivo.abrir_carpeta(_inc("otra", "9"))


def test_pantalla_documentos_escaneados():
    a = _inc()
    verificacion.guardar_archivo_digital(a, rd.DOC_CERTIFICADO, "cert.png", b"\x89PNG")

    def script():
        from core import database
        from core.seguridad import Sesion
        from modulos.archivo import interfaz
        database.init_db()
        interfaz.render(Sesion("aux", "Auxiliar de administración de personal"))
    at = AppTest.from_function(script, default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    assert any("Incapacidad de jean" in o for o in at.selectbox(key="arc_doc_sel").options)
    at.text_input(key="arc_buscar").set_value("zzz").run()                          # búsqueda sin resultados
    assert not at.exception, at.exception


# ------------------------------------------------------------------ líder
def test_lider_comparacion_tolerante_y_explicacion():
    _inc("jean", "1", jefe="  ÁLVARO  Pérez ")
    _inc("ana", "2", jefe="otro")
    lider = seguridad.Sesion("alvaro perez", seguridad.ROL_LIDER)
    assert [i["colaborador"] for i in recepcion.listar(lider)] == ["jean"]
    assert recepcion.cantidad_fuera_del_equipo(lider) == 1
    sin_equipo = seguridad.Sesion("usuario", seguridad.ROL_LIDER)
    assert recepcion.listar(sin_equipo) == [] and recepcion.cantidad_fuera_del_equipo(sin_equipo) == 2

    def script():
        from core import database
        from core.seguridad import Sesion
        from modulos.recepcion import interfaz
        database.init_db()
        interfaz.render(Sesion("usuario", "Líder"))
    at = AppTest.from_function(script, default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    mensajes = " ".join(i.value for i in at.info)
    assert "Jefe inmediato" in mensajes and "2 incapacidad" in mensajes
