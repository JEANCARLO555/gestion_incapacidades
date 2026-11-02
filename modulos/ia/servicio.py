"""
Análisis de información con IA (nota final del procedimiento).

Dos niveles:
  1. Analítica local con pandas (siempre disponible): rechazos y tiempos de pago
     por entidad, ausentismo por área y alertas de datos atípicos.
  2. Preguntas en lenguaje natural con un modelo de IA (opcional): requiere la
     variable de entorno ANTHROPIC_API_KEY. Al modelo solo se le envían
     datos AGREGADOS y ANÓNIMOS: nunca nombres, documentos ni diagnósticos.
"""
import json
import os

import pandas as pd

from config import reglas_documentos as rd
from modulos.ia import repositorio as repo

MODELO_POR_DEFECTO = "claude-sonnet-5-5"
INCAPACIDADES_FRECUENTES = 3      # N incapacidades dentro de la ventana = alerta
VENTANA_FRECUENCIA_DIAS = 90


def _df_incapacidades() -> pd.DataFrame:
    df = pd.DataFrame(repo.incapacidades_con_colaborador())
    for col in ("fecha_inicio", "fecha_fin", "fecha_recepcion"):
        if col in df:
            df[col] = pd.to_datetime(df[col])
    return df


def indicadores_por_entidad() -> pd.DataFrame:
    """Tasa de rechazo y días promedio entre transcripción y pago, por entidad."""
    inc = _df_incapacidades()
    if inc.empty:
        return pd.DataFrame(columns=["entidad", "incapacidades", "rechazadas", "tasa_rechazo_pct",
                                     "dias_promedio_a_pago"])
    rechazadas = {r["incapacidad_id"] for r in repo.rechazos()}
    hist = pd.DataFrame(repo.historial())
    dias_pago = {}
    if not hist.empty:
        hist["fecha"] = pd.to_datetime(hist["fecha"])
        primera = hist.groupby(["incapacidad_id", "estado_nuevo"])["fecha"].min().unstack()
        if {"Transcrita", "Pagada"} <= set(primera.columns):
            d = (primera["Pagada"] - primera["Transcrita"]).dt.days.dropna()
            dias_pago = d.to_dict()
    filas = []
    for entidad, grupo in inc.groupby("entidad"):
        ids = set(grupo["id"])
        tiempos = [dias_pago[i] for i in ids if i in dias_pago]
        filas.append({"entidad": entidad, "incapacidades": len(ids), "rechazadas": len(ids & rechazadas),
                      "tasa_rechazo_pct": round(len(ids & rechazadas) / len(ids) * 100, 1),
                      "dias_promedio_a_pago": round(sum(tiempos) / len(tiempos), 1) if tiempos else None})
    return pd.DataFrame(filas).sort_values("tasa_rechazo_pct", ascending=False)


def ausentismo_por_area() -> pd.DataFrame:
    inc = _df_incapacidades()
    if inc.empty:
        return pd.DataFrame(columns=["area", "incapacidades", "dias"])
    g = inc.assign(area=inc["area"].fillna("Sin área")).groupby("area").agg(
        incapacidades=("id", "count"), dias=("dias", "sum"))
    return g.reset_index().sort_values("dias", ascending=False)


def anomalias() -> list[dict]:
    """Datos atípicos para que una persona los revise (no son conclusiones)."""
    inc = _df_incapacidades()
    alertas = []
    if inc.empty:
        return alertas
    for colab, g in inc.groupby("colaborador_id"):
        g = g.sort_values("fecha_inicio")
        inicios = list(g["fecha_inicio"])
        for k in range(len(inicios) - INCAPACIDADES_FRECUENTES + 1):
            if (inicios[k + INCAPACIDADES_FRECUENTES - 1] - inicios[k]).days <= VENTANA_FRECUENCIA_DIAS:
                alertas.append({"tipo": "Incapacidades frecuentes", "colaborador": g.iloc[0]["colaborador"],
                                "detalle": f"{INCAPACIDADES_FRECUENTES} incapacidades iniciadas en "
                                           f"{VENTANA_FRECUENCIA_DIAS} días (desde {inicios[k].date()})."})
                break
        filas = g.to_dict("records")
        for a in range(len(filas)):
            for b in range(a + 1, len(filas)):
                x, y = filas[a], filas[b]
                if y["prorroga_de"] == x["id"] or x["prorroga_de"] == y["id"]:
                    continue
                if x["fecha_inicio"] <= y["fecha_fin"] and y["fecha_inicio"] <= x["fecha_fin"]:
                    alertas.append({"tipo": "Fechas traslapadas", "colaborador": x["colaborador"],
                                    "detalle": f"#{x['id']} y #{y['id']} se cruzan y no son prórroga."})
    for f in inc.to_dict("records"):
        if f["fecha_recepcion"] < f["fecha_inicio"]:
            alertas.append({"tipo": "Recepción antes del inicio", "colaborador": f["colaborador"],
                            "detalle": f"#{f['id']} se recibió antes de la fecha de inicio."})
        elif (f["fecha_recepcion"] - f["fecha_inicio"]).days > rd.DIAS_MAXIMOS_ENVIO_COLABORADOR:
            alertas.append({"tipo": "Recepción tardía", "colaborador": f["colaborador"],
                            "detalle": f"#{f['id']} se recibió {(f['fecha_recepcion'] - f['fecha_inicio']).days} "
                                       "días después del inicio."})
    return alertas


def contexto_anonimo() -> dict:
    """Resumen agregado y anónimo que es lo único que se envía al modelo."""
    inc = _df_incapacidades()
    return {
        "total_incapacidades": int(len(inc)),
        "por_estado": inc["estado"].value_counts().to_dict() if not inc.empty else {},
        "por_tipo": inc["tipo"].value_counts().to_dict() if not inc.empty else {},
        "por_entidad": indicadores_por_entidad().to_dict("records"),
        "por_area": ausentismo_por_area().to_dict("records"),
        "alertas_por_tipo": pd.Series([a["tipo"] for a in anomalias()], dtype=object).value_counts().to_dict(),
    }


def ia_disponible() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def consultar(pregunta: str) -> str:
    if not pregunta.strip():
        raise ValueError("Escriba una pregunta.")
    if not ia_disponible():
        return ("La consulta con IA no está activa. Defina la variable de entorno ANTHROPIC_API_KEY "
                "para usarla. Mientras tanto, los indicadores de arriba se calculan localmente.")
    try:
        import anthropic
    except ImportError:
        return "Falta instalar la librería: pip install anthropic"
    cliente = anthropic.Anthropic()
    respuesta = cliente.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", MODELO_POR_DEFECTO), max_tokens=1000,
        system=("Eres analista de Gestión Humana. Responde en español, de forma breve y solo con los datos "
                "agregados que se te entregan. Si el dato no está, dilo. No inventes cifras."),
        messages=[{"role": "user", "content": f"Datos agregados:\n{json.dumps(contexto_anonimo(), ensure_ascii=False, default=str)}"
                                              f"\n\nPregunta: {pregunta}"}])
    return "".join(b.text for b in respuesta.content if getattr(b, "type", "") == "text")
