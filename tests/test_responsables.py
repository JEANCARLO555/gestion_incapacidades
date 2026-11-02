"""Los roles y módulos de la aplicación deben ser coherentes con la tabla 7 del procedimiento."""
from config import responsables as r
from core import seguridad
from modulos import REGISTRO

CLAVES = {c for c, _, _ in REGISTRO}


def test_tabla_tiene_los_16_pasos_en_orden():
    assert [p["no"] for p in r.PASOS] == list(range(1, 17))
    assert all(p["responsables"] and p["modulos"] and p["descripcion"] and p["en_app"] for p in r.PASOS)


def test_los_modulos_citados_existen_y_todo_modulo_tiene_explicacion():
    assert {m for p in r.PASOS for m in p["modulos"]} <= CLAVES
    for clave in CLAVES:
        assert r.pasos_de_modulo(clave) or clave in r.SECCIONES_SIN_PASO, clave
        if clave in r.SECCIONES_SIN_PASO:
            assert "Administración de Personal" in r.nota_sin_pasos(clave)


def test_cada_rol_tiene_descripcion_y_su_responsable_existe_en_la_tabla():
    assert set(seguridad.DESCRIPCION_ROL) == set(seguridad.ROLES)
    nombres_tabla = {n for p in r.PASOS for n in p["responsables"]}
    for rol, nombre in seguridad.RESPONSABLE_EN_PROCEDIMIENTO.items():
        assert nombre in nombres_tabla, rol
    # Coordinación y SG-SST son los únicos roles que no salen de la columna Responsable
    assert set(seguridad.ROLES) - set(seguridad.RESPONSABLE_EN_PROCEDIMIENTO) == {
        seguridad.ROL_COORDINACION, seguridad.ROL_SST}


def test_cada_responsable_puede_abrir_algun_modulo_de_sus_pasos():
    for rol, nombre in seguridad.RESPONSABLE_EN_PROCEDIMIENTO.items():
        for paso in r.pasos_de_responsable(nombre):
            assert any(seguridad.puede_ver_modulo(rol, m) for m in paso["modulos"]), (rol, paso["no"])


def test_el_cobro_persuasivo_no_es_de_cartera_ni_de_juridica():
    assert seguridad.ROL_CARTERA not in seguridad.ROLES_COBRO_PERSUASIVO
    assert seguridad.puede_ver_modulo(seguridad.ROL_CARTERA, "cartera")
    assert not seguridad.puede_ver_modulo(seguridad.ROL_CARTERA, "juridico")
    assert seguridad.puede_ver_modulo(seguridad.ROL_JURIDICA, "juridico")
