"""
Reporte de ausentismo para el SG-SST (paso 6).

Se envía por correo en los primeros 3 días de cada mes. El reporte NO incluye
diagnósticos ni datos clínicos: solo fechas, tipo, entidad y días.
"""
from datetime import date

import pandas as pd

from config import settings
from core import auditoria, notificaciones
from core.utils import a_fecha, primer_dia_mes, ultimo_dia_mes
from modulos.ausentismo import repositorio as repo

DIA_LIMITE_ENVIO = 3


def _periodo(anio: int, mes: int) -> str:
    return f"{anio}-{mes:02d}"


def plazo_envio(anio: int, mes: int) -> date:
    """Primeros 3 días del mes siguiente al reportado."""
    return date(anio + (mes == 12), mes % 12 + 1, DIA_LIMITE_ENVIO)


def indicadores(anio: int, mes: int) -> dict:
    ini, fin = primer_dia_mes(anio, mes), ultimo_dia_mes(anio, mes)
    filas = []
    for r in repo.incapacidades_del_periodo(ini.isoformat(), fin.isoformat()):
        desde, hasta = max(a_fecha(r["fecha_inicio"]), ini), min(a_fecha(r["fecha_fin"]), fin)
        filas.append({**r, "dias_en_mes": (hasta - desde).days + 1})
    detalle = pd.DataFrame(filas, columns=["id", "colaborador", "area", "tipo", "entidad",
                                           "fecha_inicio", "fecha_fin", "dias_en_mes"])
    dias_calendario = (fin - ini).days + 1
    activos = repo.colaboradores_activos()
    perdidos = int(detalle["dias_en_mes"].sum()) if not detalle.empty else 0
    indice = round(perdidos / (activos * dias_calendario) * 100, 2) if activos else 0.0

    def agrupar(col):
        if detalle.empty:
            return pd.DataFrame(columns=[col, "incapacidades", "dias"])
        g = detalle.groupby(col, dropna=False).agg(incapacidades=("id", "count"), dias=("dias_en_mes", "sum"))
        return g.reset_index().sort_values("dias", ascending=False)

    return {"detalle": detalle, "por_tipo": agrupar("tipo"), "por_entidad": agrupar("entidad"),
            "por_area": agrupar("area"),
            "totales": {"incapacidades": len(detalle), "dias_perdidos": perdidos,
                        "colaboradores_activos": activos, "indice_ausentismo_pct": indice}}


def exportar_excel(anio: int, mes: int, usuario="sistema") -> str:
    ind = indicadores(anio, mes)
    settings.REPORTES_DIR.mkdir(parents=True, exist_ok=True)
    ruta = settings.REPORTES_DIR / f"ausentismo_{_periodo(anio, mes)}.xlsx"
    with pd.ExcelWriter(ruta) as w:
        pd.DataFrame([ind["totales"]]).to_excel(w, sheet_name="Resumen", index=False)
        ind["detalle"].drop(columns=["id"]).to_excel(w, sheet_name="Detalle", index=False)
        ind["por_tipo"].to_excel(w, sheet_name="Por tipo", index=False)
        ind["por_entidad"].to_excel(w, sheet_name="Por entidad", index=False)
        ind["por_area"].to_excel(w, sheet_name="Por área", index=False)
    auditoria.registrar(usuario, "exportar ausentismo", "periodo", None, _periodo(anio, mes))
    return str(ruta)


def registrar_envio(anio: int, mes: int, usuario="sistema") -> str:
    periodo = _periodo(anio, mes)
    if repo.reporte_enviado(periodo):
        raise ValueError("El reporte de ese mes ya fue registrado como enviado.")
    ruta = exportar_excel(anio, mes, usuario)
    t = indicadores(anio, mes)["totales"]
    notificaciones.crear(
        "Ausentismo", "SG-SST", "SG-SST", f"Reporte de ausentismo {periodo}",
        f"Se adjunta el reporte de ausentismo de {periodo}: {t['incapacidades']} incapacidades, "
        f"{t['dias_perdidos']} días perdidos, índice {t['indice_ausentismo_pct']} %.\nArchivo: {ruta}",
        correo=settings.CORREO_SG_SST, usuario=usuario)
    repo.guardar_envio({"periodo": periodo, "archivo": ruta, "fecha_envio": date.today().isoformat(),
                        "usuario": usuario})
    return ruta


def enviar_por_correo(anio: int, mes: int, destinatarios_texto: str, usuario="sistema") -> tuple[str, list[str]]:
    """Genera el Excel del mes y lo envía adjunto a los correos indicados."""
    correos = notificaciones.validar_correos(destinatarios_texto)
    periodo = _periodo(anio, mes)
    ruta = exportar_excel(anio, mes, usuario)
    t = indicadores(anio, mes)["totales"]
    asunto = f"Reporte de ausentismo {periodo} - {settings.NOMBRE_EMPRESA}"
    cuerpo = (f"Se adjunta el reporte de ausentismo de {periodo}.\n\n"
              f"Incapacidades: {t['incapacidades']}\nDías perdidos: {t['dias_perdidos']}\n"
              f"Colaboradores activos: {t['colaboradores_activos']}\n"
              f"Índice de ausentismo: {t['indice_ausentismo_pct']} %\n\n"
              "El archivo contiene información confidencial de los colaboradores; no lo reenvíe a "
              "personas no autorizadas.")
    notificaciones.enviar_correo(correos, asunto, cuerpo, [ruta])
    notificaciones.registrar_envio_directo("Ausentismo", correos, asunto, cuerpo + f"\n\nAdjunto: {ruta}", usuario)
    notificaciones.guardar_destinatarios(", ".join(correos))
    if not repo.reporte_enviado(periodo):
        repo.guardar_envio({"periodo": periodo, "archivo": ruta, "fecha_envio": date.today().isoformat(),
                            "usuario": usuario})
    auditoria.registrar(usuario, "enviar ausentismo por correo", "periodo", None,
                        f"{periodo} -> {', '.join(correos)}")
    return ruta, correos


def reporte_pendiente(hoy: date | None = None) -> dict | None:
    """Si estamos en los primeros 3 días del mes y falta enviar el del mes anterior."""
    hoy = hoy or date.today()
    anio, mes = (hoy.year - 1, 12) if hoy.month == 1 else (hoy.year, hoy.month - 1)
    if repo.reporte_enviado(_periodo(anio, mes)):
        return None
    return {"anio": anio, "mes": mes, "plazo": plazo_envio(anio, mes),
            "vencido": hoy > plazo_envio(anio, mes)}
