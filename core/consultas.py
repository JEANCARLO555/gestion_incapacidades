"""Lecturas compartidas por varios módulos (colaboradores, casos, liquidación)."""
from datetime import timedelta

from config import reglas_pago
from core import database as db
from core.utils import a_fecha

SELECT_INCAPACIDAD = """
SELECT i.*, c.nombre AS colaborador, c.documento, c.ibc, c.area, c.cargo,
       c.jefe_inmediato, c.correo
FROM incapacidades i JOIN colaboradores c ON c.id = i.colaborador_id
"""


# ---------------------------------------------------------------- colaboradores
def listar_colaboradores(solo_activos: bool = True) -> list[dict]:
    sql = "SELECT * FROM colaboradores"
    if solo_activos:
        sql += " WHERE activo = 1"
    return db.fetch_all(sql + " ORDER BY nombre")


def obtener_colaborador(colaborador_id: int) -> dict | None:
    return db.fetch_one("SELECT * FROM colaboradores WHERE id = ?", (colaborador_id,))


# ---------------------------------------------------------------- incapacidades
def obtener_incapacidad(inc_id: int) -> dict | None:
    return db.fetch_one(SELECT_INCAPACIDAD + " WHERE i.id = ?", (inc_id,))


def listar_incapacidades(estados=None, entidad=None, jefe=None, colaborador_id=None,
                         tipo=None, orden: str = "i.fecha_inicio DESC, i.id DESC") -> list[dict]:
    donde, params = [], []
    if estados:
        donde.append(f"i.estado IN ({','.join('?' for _ in estados)})")
        params += list(estados)
    if entidad:
        donde.append("i.entidad = ?")
        params.append(entidad)
    if jefe:
        donde.append("c.jefe_inmediato = ?")
        params.append(jefe)
    if colaborador_id:
        donde.append("i.colaborador_id = ?")
        params.append(colaborador_id)
    if tipo:
        donde.append("i.tipo = ?")
        params.append(tipo)
    sql = SELECT_INCAPACIDAD + (" WHERE " + " AND ".join(donde) if donde else "")
    return db.fetch_all(f"{sql} ORDER BY {orden}", tuple(params))


def documentos_de(inc_id: int) -> list[dict]:
    return db.fetch_all(
        "SELECT * FROM documentos_incapacidad WHERE incapacidad_id = ? ORDER BY id", (inc_id,))


def gestiones_de(inc_id: int, tipo: str | None = None, etapa: str | None = None) -> list[dict]:
    sql, params = "SELECT * FROM gestiones_cobro WHERE incapacidad_id = ?", [inc_id]
    if tipo:
        sql += " AND tipo = ?"
        params.append(tipo)
    if etapa:
        sql += " AND etapa = ?"
        params.append(etapa)
    return db.fetch_all(sql + " ORDER BY fecha, id", tuple(params))


# ---------------------------------------------------------------- casos (prórrogas)
# Una prórroga es una incapacidad que continúa a otra (`prorroga_de`). Todas las
# incapacidades encadenadas forman un "caso" y sus días se suman.
def caso_id_de(inc_id: int) -> int:
    actual = inc_id
    while True:
        fila = db.fetch_one("SELECT prorroga_de FROM incapacidades WHERE id = ?", (actual,))
        if not fila or not fila["prorroga_de"]:
            return actual
        actual = fila["prorroga_de"]


def eslabones_del_caso(caso_id: int) -> list[dict]:
    """Todas las incapacidades del caso, de la más antigua a la más reciente."""
    ids, pendientes = [], [caso_id]
    while pendientes:
        actual = pendientes.pop()
        ids.append(actual)
        hijos = db.fetch_all("SELECT id FROM incapacidades WHERE prorroga_de = ?", (actual,))
        pendientes += [h["id"] for h in hijos]
    marcas = ",".join("?" for _ in ids)
    return db.fetch_all(f"{SELECT_INCAPACIDAD} WHERE i.id IN ({marcas}) "
                        "ORDER BY i.fecha_inicio, i.id", tuple(ids))


def ancestros(inc_id: int) -> list[dict]:
    """Incapacidades anteriores de las que esta es prórroga (más antigua primero)."""
    cadena, actual = [], obtener_incapacidad(inc_id)
    while actual and actual["prorroga_de"]:
        actual = obtener_incapacidad(actual["prorroga_de"])
        if actual:
            cadena.append(actual)
    return list(reversed(cadena))


def dias_previos(inc_id: int) -> int:
    return sum(a["dias"] for a in ancestros(inc_id))


def acumulado_caso_a_fecha(caso_id: int, fecha) -> int:
    """Días de incapacidad acumulados del caso hasta una fecha (inclusive)."""
    corte, total = a_fecha(fecha), 0
    for e in eslabones_del_caso(caso_id):
        ini, fin = a_fecha(e["fecha_inicio"]), a_fecha(e["fecha_fin"])
        total += max(0, (min(corte, fin) - ini).days + 1)
    return total


# ---------------------------------------------------------------- liquidación
def aplica_liquidacion(inc: dict) -> bool:
    return inc["tipo"] in reglas_pago.TIPOS_CON_REGLA


def liquidacion_diaria(inc_id: int) -> list[dict]:
    """Un renglón por día de la incapacidad, con quién paga y cuánto (5.5.2)."""
    inc = obtener_incapacidad(inc_id)
    if not inc or not aplica_liquidacion(inc):
        return []
    inicio = a_fecha(inc["fecha_inicio"])
    filas = reglas_pago.liquidar_dias(inc["ibc"], dias_previos(inc_id), inc["dias"])
    for k, fila in enumerate(filas):
        fila["fecha"] = inicio + timedelta(days=k)
    return filas


def resumen_liquidacion(inc_id: int) -> dict:
    inc = obtener_incapacidad(inc_id)
    if not inc:
        raise ValueError("Incapacidad no encontrada.")
    if not aplica_liquidacion(inc):
        return {"aplica": False,
                "motivo": f"El procedimiento no define el cálculo para «{inc['tipo']}»."}
    diario = liquidacion_diaria(inc_id)
    tramos: dict = {}
    for d in diario:
        clave = (d["responsable"], d["porcentaje"])
        t = tramos.setdefault(clave, {"responsable": d["responsable"],
                                      "porcentaje": d["porcentaje"], "dias": 0, "valor": 0.0})
        t["dias"] += 1
        t["valor"] += d["valor"] or 0.0
    valor_empresa = sum(t["valor"] for t in tramos.values() if t["responsable"] == reglas_pago.EMPRESA)
    valor_eps = sum(t["valor"] for t in tramos.values() if t["responsable"] == reglas_pago.EPS)
    dias_colab = sum(t["dias"] for t in tramos.values()
                     if t["responsable"] == reglas_pago.TRAMITE_COLABORADOR)
    return {"aplica": True, "dias_previos": dias_previos(inc_id),
            "valor_dia": reglas_pago.valor_dia(inc["ibc"]),
            "tramos": list(tramos.values()),
            "valor_empresa": round(valor_empresa, 2), "valor_eps": round(valor_eps, 2),
            "dias_tramite_colaborador": dias_colab,
            "total_trabajador": round(valor_empresa + valor_eps, 2)}


def pagado_a_incapacidad(inc_id: int) -> float:
    fila = db.fetch_one("SELECT COALESCE(SUM(valor),0) AS t FROM pagos_aplicaciones "
                        "WHERE incapacidad_id = ?", (inc_id,))
    return float(fila["t"])
