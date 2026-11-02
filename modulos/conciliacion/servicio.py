"""
Conciliación de pagos (5.5, 5.5.1 y pasos 12 y 13).

Contabilidad informa lo que las entidades consignaron; el auxiliar identifica a
qué colaborador e incapacidad corresponde cada pago. Una consignación puede pagar
varias incapacidades. Lo que no se logra identificar se avisa a Contabilidad.
"""
from datetime import date

import pandas as pd

from config import estados, settings
from core import auditoria, consultas, notificaciones
from core.utils import a_fecha, moneda, primer_dia_mes, ultimo_dia_mes
from modulos.conciliacion import repositorio as repo

ESTADOS_CONCILIABLES = [estados.TRANSCRITA, estados.COBRADA, estados.EN_CARTERA,
                        estados.EN_JURIDICO, estados.PAGADA]


def registrar_pago(entidad: str, fecha_pago, valor: float, referencia: str = "",
                   usuario="sistema", nota: str = "") -> int:
    if entidad not in settings.ENTIDADES:
        raise ValueError("Entidad no válida.")
    if valor <= 0:
        raise ValueError("El valor del pago debe ser mayor a cero.")
    pid = repo.insertar_pago({"entidad": entidad, "fecha_pago": a_fecha(fecha_pago).isoformat(),
                              "valor_total": float(valor), "referencia": referencia.strip(),
                              "nota": nota.strip(), "usuario": usuario})
    auditoria.registrar(usuario, "pago de entidad", "pago", pid, f"{entidad} {moneda(valor)}")
    return pid


def sin_identificar(pago: dict) -> float:
    return round(pago["valor_total"] - repo.aplicado_a_pago(pago["id"]), 2)


def aplicar_pago(pago_id: int, incapacidad_id: int, valor: float, usuario="sistema",
                 dias_pagados: int | None = None) -> int:
    """Asigna (todo o parte de) un pago a una incapacidad. Lo que manda es el detalle de la entidad:
    no se exige que el valor coincida con el cálculo del sistema."""
    pago = repo.obtener_pago(pago_id)
    inc = consultas.obtener_incapacidad(incapacidad_id)
    if not pago or not inc:
        raise ValueError("Pago o incapacidad no encontrados.")
    if pago["entidad"] != inc["entidad"]:
        raise ValueError(f"El pago es de {pago['entidad']} y la incapacidad es de {inc['entidad']}.")
    if valor <= 0:
        raise ValueError("El valor debe ser mayor a cero.")
    if valor > sin_identificar(pago) + 0.01:
        raise ValueError(f"Solo quedan {moneda(sin_identificar(pago))} por identificar en este pago.")
    if dias_pagados is not None and not 0 <= dias_pagados <= inc["dias"]:
        raise ValueError(f"Los días pagados deben estar entre 0 y {inc['dias']}.")
    aid = repo.insertar_aplicacion({"pago_id": pago_id, "incapacidad_id": incapacidad_id,
                                    "valor": float(valor), "dias_pagados": dias_pagados or None,
                                    "usuario": usuario})
    auditoria.registrar(usuario, "identificar pago", "incapacidad", incapacidad_id, moneda(valor))
    return aid


def pagos_pendientes() -> list[dict]:
    return [{**p, "sin_identificar": sin_identificar(p)} for p in repo.listar_pagos()
            if sin_identificar(p) > 0.01]


def esperado_eps(inc: dict) -> float | None:
    r = consultas.resumen_liquidacion(inc["id"])
    return r["valor_eps"] if r["aplica"] else None


def motivo_sin_valor(inc: dict) -> str | None:
    """Por qué el sistema no puede calcular lo que debe pagar la EPS (None si sí puede)."""
    if not consultas.aplica_liquidacion(inc):
        return f"El procedimiento no define el cálculo para «{inc['tipo']}»."
    if not inc["ibc"]:
        return "El IBC del colaborador está en $0: edítelo en Recepción → Colaboradores."
    if (esperado_eps(inc) or 0) <= 0:
        return "Todos sus días los paga la empresa (2 días o menos) o van después del día 180."
    return None


def sugerencias(pago_id: int, maximo: int | None = 15) -> list[dict]:
    """Incapacidades de la misma entidad. Primero las de saldo parecido al pago; luego las demás.

    El valor calculado es solo una ayuda: el detalle que entrega la entidad es lo que manda,
    por eso también se ofrecen las incapacidades sin valor calculado."""
    pago = repo.obtener_pago(pago_id)
    disponible = sin_identificar(pago)
    con_valor, sin_valor = [], []
    for inc in consultas.listar_incapacidades(estados=ESTADOS_CONCILIABLES, entidad=pago["entidad"]):
        motivo = motivo_sin_valor(inc)
        pagado = consultas.pagado_a_incapacidad(inc["id"])
        if motivo:
            sin_valor.append({**inc, "esperado": None, "saldo": None, "coincidencia": None,
                              "pagado": pagado, "motivo": "Sin valor calculado: " + motivo})
            continue
        esperado = esperado_eps(inc)
        saldo = round(esperado - pagado, 2)
        coincidencia = round(1 - abs(saldo - disponible) / max(abs(saldo), disponible, 1), 3)
        con_valor.append({**inc, "esperado": esperado, "saldo": saldo, "coincidencia": coincidencia,
                          "pagado": pagado, "motivo": "Ya está pagada por completo" if saldo <= 0.01 else ""})
    con_valor.sort(key=lambda f: (f["saldo"] <= 0.01, -f["coincidencia"]))
    resultado = con_valor + sorted(sin_valor, key=lambda f: f["fecha_inicio"], reverse=True)
    return resultado if maximo is None else resultado[:maximo]


def diagnostico_entidad(entidad: str) -> list[str]:
    """Explica por qué no hay incapacidades para asignar un pago de esa entidad."""
    todas = consultas.listar_incapacidades(entidad=entidad)
    if not todas:
        return [f"No hay ninguna incapacidad registrada con la entidad «{entidad}». Revise que la entidad "
                "de la incapacidad sea la misma del pago."]
    mensajes = []
    por_estado: dict = {}
    for inc in todas:
        if inc["estado"] not in ESTADOS_CONCILIABLES:
            por_estado[inc["estado"]] = por_estado.get(inc["estado"], 0) + 1
    for estado, n in por_estado.items():
        mensajes.append(f"{n} incapacidad(es) de {entidad} siguen en estado «{estado}»: todavía deben "
                        "pasar por Verificación y Transcripción antes de recibir pagos.")
    return mensajes


def saldos_por_entidad() -> list[dict]:
    """Cuánto debe cada entidad: lo esperado según la liquidación menos lo pagado (estimado)."""
    acumulado: dict = {}
    for inc in consultas.listar_incapacidades(estados=ESTADOS_CONCILIABLES):
        fila = acumulado.setdefault(inc["entidad"], {"entidad": inc["entidad"], "esperado": 0.0,
                                                     "pagado": 0.0, "incapacidades": 0, "sin_valor": 0})
        fila["incapacidades"] += 1
        fila["pagado"] += consultas.pagado_a_incapacidad(inc["id"])
        if motivo_sin_valor(inc):
            fila["sin_valor"] += 1
        else:
            fila["esperado"] += esperado_eps(inc)
    for f in acumulado.values():
        f["saldo"] = round(f["esperado"] - f["pagado"], 2)
    return sorted(acumulado.values(), key=lambda f: -f["saldo"])


def reporte_mensual(anio: int, mes: int) -> pd.DataFrame:
    """Detalle por entidad: colaborador, días, fechas de la incapacidad y valor pagado (paso 5.5)."""
    filas = repo.aplicaciones_del_mes(primer_dia_mes(anio, mes).isoformat(),
                                      ultimo_dia_mes(anio, mes).isoformat())
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    df["periodo_causacion"] = df["fecha_inicio"] + " a " + df["fecha_fin"]
    return df.rename(columns={"entidad": "Entidad", "colaborador": "Colaborador", "dias": "Días de la incapacidad", "dias_pagados": "Días pagados",
                              "periodo_causacion": "Periodo de causación", "valor": "Valor pagado",
                              "fecha_pago": "Fecha de pago", "referencia": "Referencia"})[
        ["Entidad", "Colaborador", "Días de la incapacidad", "Días pagados", "Periodo de causación",
         "Valor pagado", "Fecha de pago", "Referencia"]]


def exportar_reporte(anio: int, mes: int) -> str:
    df = reporte_mensual(anio, mes)
    if df.empty:
        raise ValueError("No hay pagos identificados en ese mes.")
    settings.REPORTES_DIR.mkdir(parents=True, exist_ok=True)
    ruta = settings.REPORTES_DIR / f"conciliacion_{anio}-{mes:02d}.xlsx"
    df.to_excel(ruta, index=False)
    return str(ruta)


def notificar_pagos_sin_identificar(usuario="sistema") -> int:
    """Si no se pueden identificar los saldos, se notifica a Contabilidad (5.5)."""
    pendientes = pagos_pendientes()
    if not pendientes:
        raise ValueError("No hay pagos por identificar.")
    lineas = [f"- {p['fecha_pago']} · {p['entidad']} · ref. {p['referencia'] or 's/n'} · "
              f"por identificar {moneda(p['sin_identificar'])}" for p in pendientes]
    return notificaciones.crear(
        "Conciliación", "Contabilidad", "Contabilidad", "Pagos de entidades sin identificar",
        "No fue posible identificar los siguientes pagos; se contactará al asesor de cada entidad:\n"
        + "\n".join(lineas), correo=settings.CORREO_CONTABILIDAD, usuario=usuario)


def pagadas_sin_pago_registrado() -> list[dict]:
    return repo.pagadas_sin_aplicacion()
