import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings  # noqa: E402
from core import database  # noqa: E402


@pytest.fixture(autouse=True)
def entorno(tmp_path, monkeypatch):
    """Cada prueba usa una base de datos y carpetas temporales."""
    monkeypatch.setattr(settings, "DB_PATH", tmp_path / "prueba.db")
    monkeypatch.setattr(settings, "ARCHIVOS_DIR", tmp_path / "archivos")
    monkeypatch.setattr(settings, "REPORTES_DIR", tmp_path / "reportes")
    monkeypatch.setattr(settings, "ENV_FILE", tmp_path / ".env")
    for var in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"):
        monkeypatch.delenv(var, raising=False)
    database.init_db()
    return tmp_path
