"""
Porcentajes de reconocimiento (5.5.2).

  Días 1 a 2      -> 100 % del IBC, lo asume la empresa
  Días 3 a 90     ->  67 % del IBC, lo asume la EPS
  Días 91 a 180   ->  50 % del IBC, lo asume la EPS
  Día 181 en adelante -> el colaborador tramita ante el fondo de pensiones o la EPS

Se cuentan DÍAS ACUMULADOS (las prórrogas suman a los días anteriores).
"""
from dataclasses import dataclass

from config import reglas_documentos as rd

EMPRESA = "Empresa"
EPS = "EPS"
TRAMITE_COLABORADOR = "Colaborador (trámite ante fondo de pensiones o EPS)"


@dataclass(frozen=True)
class Tramo:
    desde: int
    hasta: int | None
    porcentaje: float | None
    responsable: str


TRAMOS = (
    Tramo(1, 2, 1.00, EMPRESA),
    Tramo(3, 90, 0.67, EPS),
    Tramo(91, 180, 0.50, EPS),
    Tramo(181, None, None, TRAMITE_COLABORADOR),
)

# Para convertir el IBC mensual en valor diario
DIAS_BASE_IBC = 30

# El procedimiento define estos porcentajes sin distinguir el tipo. Se aplican
# solo a incapacidades de origen común. Para accidente laboral (ARL) y licencias
# el procedimiento no define el cálculo, por eso NO se liquidan (ver README).
TIPOS_CON_REGLA = {rd.TIPO_ENFERMEDAD_GENERAL, rd.TIPO_ACCIDENTE_TRANSITO}


def tramo_para_dia(dia_acumulado: int) -> Tramo:
    for tramo in TRAMOS:
        if dia_acumulado >= tramo.desde and (tramo.hasta is None or dia_acumulado <= tramo.hasta):
            return tramo
    raise ValueError(f"Día acumulado inválido: {dia_acumulado}")


def valor_dia(ibc: float) -> float:
    return float(ibc) / DIAS_BASE_IBC


def liquidar_dias(ibc: float, dias_previos: int, dias: int) -> list[dict]:
    """Devuelve un renglón por día: número de día acumulado, responsable, % y valor."""
    vd = valor_dia(ibc)
    filas = []
    for k in range(dias):
        n = dias_previos + k + 1
        t = tramo_para_dia(n)
        valor = round(vd * t.porcentaje, 2) if t.porcentaje is not None else None
        filas.append({"dia_acumulado": n, "responsable": t.responsable,
                      "porcentaje": t.porcentaje, "valor": valor})
    return filas
