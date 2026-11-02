"""
Novedades de nómina (5.2).

Una vez transcrita la incapacidad, Administración de personal gestiona la novedad
de nómina: cuántos días y cuánto valor corresponde a la empresa y a la EPS en cada
mes, y desde qué día (181) se suspende el pago por nómina.
"""
from collections import defaultdict
from datetime import date

import pandas as pd

from config import estados, reglas_pago, settings
from core import auditoria, consultas
from modulos.nomina import repositorio as repo


def _periodo(anio: int, mes: int) -> str:
    return f"{anio}-{mes:02d}"


def generar_novedades(anio: int, mes: int, usuario="sistema") -> dict:
    """Calcula las novedades del mes. No modifica las que ya fueron reportadas."""
    periodo = _periodo(anio, mes)
    generadas, sin_regla, ya_reportadas = 0, [], 0
    for inc in consultas.listar_incapacidades(estados=sorted(estados.ESTADOS_CON_NOVEDAD_NOMINA)):
        diario = [d for d in consultas.liquidacion_diaria(inc["id"])
                  if d["fecha"].year == anio and d["fecha"].month == mes]
        if not consultas.aplica_liquidacion(inc):
            if inc["fecha_inicio"][:7] <= periodo <= inc["fecha_fin"][:7]:
                sin_regla.append(inc["id"])
            continue
        if not diario:
            continue
        previa = repo.obtener(inc["id"], periodo)
        if previa and previa["reportada"]:
            ya_reportadas += 1
            continue
        repo.guardar({
            "incapacidad_id": inc["id"], "periodo": periodo, "dias": len(diario),
            "dias_empresa": sum(d["responsable"] == reglas_pago.EMPRESA for d in diario),
            "dias_eps": sum(d["responsable"] == reglas_pago.EPS for d in diario),
            "dias_sin_pago_nomina": sum(d["responsable"] == reglas_pago.TRAMITE_COLABORADOR for d in diario),
            "valor_empresa": round(sum(d["valor"] or 0 for d in diario if d["responsable"] == reglas_pago.EMPRESA), 2),
            "valor_eps": round(sum(d["valor"] or 0 for d in diario if d["responsable"] == reglas_pago.EPS), 2)})
        generadas += 1
    auditoria.registrar(usuario, "generar novedades de nómina", "periodo", None, periodo)
    return {"generadas": generadas, "sin_regla": sin_regla, "ya_reportadas": ya_reportadas}


def novedades(anio: int, mes: int) -> list[dict]:
    return repo.listar_periodo(_periodo(anio, mes))


def marcar_reportadas(anio: int, mes: int, usuario="sistema") -> int:
    n = 0
    for nov in repo.listar_periodo(_periodo(anio, mes)):
        if not nov["reportada"]:
            repo.marcar_reportada(nov["id"], date.today().isoformat())
            n += 1
    auditoria.registrar(usuario, "reportar novedades de nómina", "periodo", None, _periodo(anio, mes))
    return n


def exportar_csv(anio: int, mes: int) -> str:
    filas = novedades(anio, mes)
    if not filas:
        raise ValueError("No hay novedades en ese periodo: genérelas primero.")
    df = pd.DataFrame(filas)[["documento", "colaborador", "tipo", "fecha_inicio", "fecha_fin", "dias",
                              "dias_empresa", "dias_eps", "dias_sin_pago_nomina",
                              "valor_empresa", "valor_eps"]]
    settings.REPORTES_DIR.mkdir(parents=True, exist_ok=True)
    ruta = settings.REPORTES_DIR / f"novedades_nomina_{_periodo(anio, mes)}.csv"
    df.to_csv(ruta, index=False, encoding="utf-8-sig")
    return str(ruta)
