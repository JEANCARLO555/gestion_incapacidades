"""
Detecta quién supera 90, 120, 150 y 180 días de incapacidad (5.5.3).

Un «caso» agrupa una incapacidad y todas sus prórrogas; los días se suman.
"""
from datetime import date, timedelta

from config import reglas_monitoreo as rm
from core import consultas
from core.utils import a_fecha, primer_dia_mes, ultimo_dia_mes
from modulos.monitoreo import repositorio as repo


def listar_casos() -> list[dict]:
    casos = []
    for cabeza in repo.incapacidades_cabeza_de_caso():
        eslabones = consultas.eslabones_del_caso(cabeza["id"])
        primero, ultimo = eslabones[0], eslabones[-1]
        if primero["tipo"] in rm.TIPOS_EXCLUIDOS_MONITOREO:
            continue
        casos.append({
            "caso_id": cabeza["id"], "ultima_id": ultimo["id"],
            "colaborador_id": primero["colaborador_id"], "colaborador": primero["colaborador"],
            "area": primero["area"], "entidad": ultimo["entidad"], "tipo": ultimo["tipo"],
            "fecha_inicio": a_fecha(primero["fecha_inicio"]),
            "fecha_fin": max(a_fecha(e["fecha_fin"]) for e in eslabones),
            "eslabones": eslabones})
    return casos


def acumulado(caso: dict, fecha) -> int:
    """Días acumulados del caso hasta `fecha` (inclusive)."""
    corte, total = a_fecha(fecha), 0
    for e in caso["eslabones"]:
        ini, fin = a_fecha(e["fecha_inicio"]), a_fecha(e["fecha_fin"])
        total += max(0, (min(corte, fin) - ini).days + 1)
    return total


def hito_superado(dias: int) -> int | None:
    """Mayor hito (90/120/150/180) que los días acumulados superan; None si ninguno."""
    superados = [h for h in rm.HITOS if dias > h]
    return max(superados) if superados else None


def casos_activos(fecha_corte=None) -> list[dict]:
    corte = a_fecha(fecha_corte) or date.today()
    activos = []
    for caso in listar_casos():
        if caso["fecha_inicio"] <= corte <= caso["fecha_fin"]:
            activos.append({**caso, "dias": acumulado(caso, corte)})
    return activos


def reporte_mensual(anio: int, mes: int) -> list[dict]:
    """Casos del mes que superan algún hito, para el reporte mensual del 5.5.3."""
    ini_mes, fin_mes = primer_dia_mes(anio, mes), ultimo_dia_mes(anio, mes)
    filas = []
    for caso in listar_casos():
        if caso["fecha_inicio"] > fin_mes or caso["fecha_fin"] < ini_mes:
            continue
        dias = acumulado(caso, min(fin_mes, caso["fecha_fin"]))
        hito = hito_superado(dias)
        if hito is None:
            continue
        filas.append({
            "caso_id": caso["caso_id"], "colaborador": caso["colaborador"], "area": caso["area"],
            "entidad": caso["entidad"], "inicio": caso["fecha_inicio"].isoformat(),
            "fin": caso["fecha_fin"].isoformat(), "dias_acumulados": dias,
            "hito_superado": hito, **{f"supera_{h}": dias > h for h in rm.HITOS}})
    return sorted(filas, key=lambda f: -f["dias_acumulados"])


def fecha_en_que_supera(caso: dict, hito: int) -> date | None:
    """Primer día en que el caso acumula MÁS de `hito` días (None si la incapacidad termina antes)."""
    dia = caso["fecha_inicio"]
    while dia <= caso["fecha_fin"]:
        if acumulado(caso, dia) > hito:
            return dia
        dia += timedelta(days=1)
    return None


def casos_del_mes(anio: int, mes: int) -> list[dict]:
    """TODOS los casos que tocan el mes, con sus días al cierre y cuándo superarán el siguiente hito."""
    ini_mes, fin_mes = primer_dia_mes(anio, mes), ultimo_dia_mes(anio, mes)
    filas = []
    for caso in listar_casos():
        if caso["fecha_inicio"] > fin_mes or caso["fecha_fin"] < ini_mes:
            continue
        dias = acumulado(caso, min(fin_mes, caso["fecha_fin"]))
        proximo = next((h for h in rm.HITOS if dias <= h), None)
        cuando = fecha_en_que_supera(caso, proximo) if proximo else None
        filas.append({
            "caso_id": caso["caso_id"], "colaborador": caso["colaborador"], "entidad": caso["entidad"],
            "inicio": caso["fecha_inicio"].isoformat(), "fin": caso["fecha_fin"].isoformat(),
            "dias_al_cierre": dias, "hito_superado": hito_superado(dias) or "—",
            "proximo_hito": proximo or "—",
            "supera_el": (cuando.isoformat() if cuando else
                          ("—" if proximo is None else "No lo alcanza: la incapacidad termina antes"))})
    return sorted(filas, key=lambda f: -f["dias_al_cierre"])
