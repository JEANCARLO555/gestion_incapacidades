"""Registro de quién hizo o consultó qué (importante: se manejan datos de salud)."""
from core import database as db


def registrar(usuario: str, accion: str, entidad: str = "", entidad_id: int | None = None,
              detalle: str = "", rol: str = "") -> None:
    db.insert("auditoria", {"usuario": usuario, "rol": rol, "accion": accion,
                            "entidad": entidad, "entidad_id": entidad_id, "detalle": detalle})


def registrar_consulta(sesion, que: str, entidad_id: int | None = None) -> None:
    """Deja huella de que alguien consultó información sensible."""
    registrar(sesion.usuario, "consulta", "datos sensibles", entidad_id, que, rol=sesion.rol)


def listar(limite: int = 500) -> list[dict]:
    return db.fetch_all("SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (limite,))
