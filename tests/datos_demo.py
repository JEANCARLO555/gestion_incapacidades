"""
Datos FICTICIOS para probar la aplicación sin usar información real.

Uso:   python -m tests.datos_demo
"""
from datetime import date, timedelta

from config import reglas_documentos as rd
from core import database
from modulos.archivo import servicio as archivo
from modulos.conciliacion import servicio as conciliacion
from modulos.recepcion import servicio as recepcion
from modulos.seguimiento_cobro import servicio as cobro
from modulos.transcripcion import servicio as transcripcion
from modulos.verificacion import servicio as verificacion

U = "demo"


def _recibir_completa(cid, tipo, entidad, ini, fin, canal="Recepción", prorroga_de=None):
    dias = (fin - ini).days + 1
    docs = rd.documentos_requeridos(tipo, dias)
    inc = recepcion.registrar_incapacidad(cid, tipo, entidad, ini, fin, canal, "Recepcionista demo",
                                          True, True, docs, fecha_recepcion=ini + timedelta(days=1),
                                          prorroga_de=prorroga_de, usuario=U)
    verificacion.verificar(inc, docs, True, U)
    return inc


def cargar(hoy: date | None = None) -> dict:
    hoy = hoy or date.today()
    database.init_db()
    ana = recepcion.registrar_colaborador("1001", "Ana Pérez (demo)", "Ejecutiva", "Comercial", "lider1",
                                          "ana@example.com", 3_000_000, U)
    carlos = recepcion.registrar_colaborador("1002", "Carlos Gómez (demo)", "Operario", "Operaciones",
                                             "lider1", "", 2_000_000, U)
    marta = recepcion.registrar_colaborador("1003", "Marta Ruiz (demo)", "Analista", "Administrativa",
                                            "lider2", "", 4_000_000, U)
    luis = recepcion.registrar_colaborador("1004", "Luis Torres (demo)", "Conductor", "Operaciones",
                                           "lider2", "", 2_500_000, U)

    # Ana: caso largo con prórroga (131 días acumulados), transcrito y cobrado
    a1 = _recibir_completa(ana, rd.TIPO_ENFERMEDAD_GENERAL, "SURA EPS", hoy - timedelta(days=130),
                           hoy - timedelta(days=41))
    a2 = _recibir_completa(ana, rd.TIPO_ENFERMEDAD_GENERAL, "SURA EPS", hoy - timedelta(days=40),
                           hoy + timedelta(days=20), prorroga_de=a1)
    for inc in (a1, a2):
        transcripcion.registrar_transcripcion(inc, hoy - timedelta(days=30), "Portal de la entidad",
                                              f"RAD-{inc}", U)
    cobro.marcar_cobrada(a1, hoy + timedelta(days=15), U, fecha_cobro=hoy - timedelta(days=25))
    pago = conciliacion.registrar_pago("SURA EPS", hoy - timedelta(days=3), 1_000_000, "CONS-001", U)

    # Carlos: llegó por correo y falta la epicrisis (verificación pendiente)
    recepcion.registrar_incapacidad(carlos, rd.TIPO_ENFERMEDAD_GENERAL, "Nueva EPS", hoy - timedelta(days=5),
                                    hoy - timedelta(days=1), "Correo electrónico", "Auxiliar demo", False,
                                    False, [rd.DOC_CERTIFICADO], usuario=U)

    # Marta: accidente laboral (el procedimiento no define el cálculo)
    m1 = _recibir_completa(marta, rd.TIPO_ACCIDENTE_LABORAL, "ARL SURA", hoy - timedelta(days=12),
                           hoy - timedelta(days=6), "Oficinas principales")

    # Luis: pagada, lista para archivo
    l1 = _recibir_completa(luis, rd.TIPO_ENFERMEDAD_GENERAL, "Nueva EPS", hoy - timedelta(days=60),
                           hoy - timedelta(days=50), "Líderes comerciales")
    transcripcion.registrar_transcripcion(l1, hoy - timedelta(days=45), "Portal de la entidad", "RAD-L", U)
    cobro.marcar_cobrada(l1, hoy - timedelta(days=10), U)
    cobro.marcar_pagada(l1, U)
    archivo.asignar_ubicacion(l1, "Carpeta Nueva EPS 01", U)
    return {"ana": ana, "a1": a1, "a2": a2, "carlos": carlos, "m1": m1, "l1": l1, "pago": pago}


if __name__ == "__main__":
    print("Datos de demostración cargados:", cargar())
