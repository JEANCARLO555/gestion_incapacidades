"""
Liquidación según los porcentajes de reconocimiento (5.5.2).

Días 1-2: 100 % empresa · 3-90: 67 % EPS · 91-180: 50 % EPS · 181+: trámite del colaborador.
Los días se acumulan entre prórrogas. La regla vive en config/reglas_pago.py.
"""
from config import reglas_pago
from core import consultas
from modulos.liquidacion import repositorio as repo


def listar() -> list[dict]:
    return repo.listar_liquidables()


def liquidar(inc_id: int) -> dict:
    return consultas.resumen_liquidacion(inc_id)


def detalle_diario(inc_id: int) -> list[dict]:
    return consultas.liquidacion_diaria(inc_id)


def simular(ibc: float, dias_previos: int, dias: int) -> list[dict]:
    """Calculadora libre: no toca la base de datos."""
    if ibc <= 0 or dias <= 0 or dias_previos < 0:
        raise ValueError("Indique un IBC y unos días mayores a cero.")
    return reglas_pago.liquidar_dias(ibc, dias_previos, dias)
