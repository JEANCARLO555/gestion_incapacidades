"""Definición de las tablas de la base de datos (SQLite)."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS colaboradores (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    documento     TEXT NOT NULL UNIQUE,
    nombre        TEXT NOT NULL,
    cargo         TEXT,
    area          TEXT,
    jefe_inmediato TEXT,
    correo        TEXT,
    ibc           REAL NOT NULL DEFAULT 0,      -- Ingreso Base de Cotización mensual
    activo        INTEGER NOT NULL DEFAULT 1,
    creado_en     TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS incapacidades (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    colaborador_id   INTEGER NOT NULL REFERENCES colaboradores(id),
    tipo             TEXT NOT NULL,
    entidad          TEXT NOT NULL,
    fecha_inicio     TEXT NOT NULL,
    fecha_fin        TEXT NOT NULL,
    dias             INTEGER NOT NULL,
    fecha_nacimiento TEXT,                       -- solo licencia de paternidad
    prorroga_de      INTEGER REFERENCES incapacidades(id),
    canal_recepcion  TEXT NOT NULL,
    recibido_por     TEXT,
    fecha_recepcion  TEXT NOT NULL,
    informo_jefe     INTEGER NOT NULL DEFAULT 0,
    llegada_fisica   INTEGER NOT NULL DEFAULT 0,
    reemplazo        TEXT,
    estado           TEXT NOT NULL,
    fecha_promesa_pago TEXT,
    deterioro_crediticio INTEGER NOT NULL DEFAULT 0,
    observaciones    TEXT,
    creado_en        TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS documentos_incapacidad (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    incapacidad_id INTEGER NOT NULL REFERENCES incapacidades(id),
    documento      TEXT NOT NULL,
    recibido       INTEGER NOT NULL DEFAULT 0,
    UNIQUE (incapacidad_id, documento)
);

CREATE TABLE IF NOT EXISTS historial_estados (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    incapacidad_id  INTEGER NOT NULL REFERENCES incapacidades(id),
    estado_anterior TEXT,
    estado_nuevo    TEXT NOT NULL,
    fecha           TEXT NOT NULL,
    usuario         TEXT,
    nota            TEXT
);

CREATE TABLE IF NOT EXISTS llamados_documentacion (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    incapacidad_id INTEGER NOT NULL REFERENCES incapacidades(id),
    numero         INTEGER NOT NULL,             -- 1 = primer aviso, 2 = segundo llamado
    fecha          TEXT NOT NULL,
    fecha_limite   TEXT,
    faltantes      TEXT,
    usuario        TEXT
);

CREATE TABLE IF NOT EXISTS archivos_digitales (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    incapacidad_id INTEGER NOT NULL REFERENCES incapacidades(id),
    tipo_documento TEXT NOT NULL,
    nombre_archivo TEXT NOT NULL,
    ruta           TEXT NOT NULL,
    es_clinico     INTEGER NOT NULL DEFAULT 0,
    eliminado_en   TEXT,
    subido_en      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    usuario        TEXT
);

CREATE TABLE IF NOT EXISTS transcripciones (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    incapacidad_id INTEGER NOT NULL REFERENCES incapacidades(id),
    fecha          TEXT NOT NULL,
    medio          TEXT NOT NULL,
    radicado       TEXT,
    evidencia      TEXT,
    fuera_de_plazo INTEGER NOT NULL DEFAULT 0,
    nota           TEXT,
    usuario        TEXT
);

CREATE TABLE IF NOT EXISTS rechazos (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    incapacidad_id INTEGER NOT NULL REFERENCES incapacidades(id),
    fecha          TEXT NOT NULL,
    causal         TEXT NOT NULL,
    improcedente   INTEGER NOT NULL DEFAULT 0,
    subsanado      INTEGER NOT NULL DEFAULT 0,
    usuario        TEXT
);

-- Seguimiento, cartera y jurídico comparten esta bitácora (campo `etapa`)
CREATE TABLE IF NOT EXISTS gestiones_cobro (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    incapacidad_id INTEGER NOT NULL REFERENCES incapacidades(id),
    etapa          TEXT NOT NULL,   -- Seguimiento | Cobro persuasivo | Cartera | Jurídico
    tipo           TEXT NOT NULL,
    fecha          TEXT NOT NULL,
    detalle        TEXT,
    radicado       TEXT,
    respondida     INTEGER NOT NULL DEFAULT 0,
    usuario        TEXT
);

CREATE TABLE IF NOT EXISTS pagos_entidad (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entidad     TEXT NOT NULL,
    fecha_pago  TEXT NOT NULL,
    valor_total REAL NOT NULL,
    referencia  TEXT,
    nota        TEXT,
    usuario     TEXT,
    creado_en   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS pagos_aplicaciones (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    pago_id        INTEGER NOT NULL REFERENCES pagos_entidad(id),
    incapacidad_id INTEGER NOT NULL REFERENCES incapacidades(id),
    valor          REAL NOT NULL,
    dias_pagados   INTEGER,                      -- según el detalle del portal de la entidad
    usuario        TEXT,
    creado_en      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS conceptos_rehabilitacion (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    caso_id             INTEGER NOT NULL UNIQUE REFERENCES incapacidades(id),
    fecha_solicitud     TEXT,
    fecha_emision       TEXT,
    resultado           TEXT,
    fecha_envio_afp     TEXT,
    fecha_comunicacion_trabajador TEXT,
    nota                TEXT,
    usuario             TEXT
);

CREATE TABLE IF NOT EXISTS reintegros (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    incapacidad_id  INTEGER NOT NULL REFERENCES incapacidades(id),
    fecha           TEXT NOT NULL,
    valor           REAL NOT NULL,
    entidad_pagadora TEXT,
    nota            TEXT,
    usuario         TEXT
);

CREATE TABLE IF NOT EXISTS nomina_novedades (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    incapacidad_id INTEGER NOT NULL REFERENCES incapacidades(id),
    periodo        TEXT NOT NULL,                -- AAAA-MM
    dias           INTEGER NOT NULL,
    dias_empresa   INTEGER NOT NULL DEFAULT 0,
    dias_eps       INTEGER NOT NULL DEFAULT 0,
    dias_sin_pago_nomina INTEGER NOT NULL DEFAULT 0,   -- del día 181 en adelante
    valor_empresa  REAL NOT NULL DEFAULT 0,
    valor_eps      REAL NOT NULL DEFAULT 0,
    reportada      INTEGER NOT NULL DEFAULT 0,
    fecha_reporte  TEXT,
    UNIQUE (incapacidad_id, periodo)
);

CREATE TABLE IF NOT EXISTS reportes_ausentismo (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    periodo     TEXT NOT NULL UNIQUE,            -- AAAA-MM
    archivo     TEXT,
    fecha_envio TEXT NOT NULL,
    usuario     TEXT
);

CREATE TABLE IF NOT EXISTS archivo_fisico (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    incapacidad_id       INTEGER NOT NULL UNIQUE REFERENCES incapacidades(id),
    ubicacion            TEXT,
    fecha_archivo        TEXT,
    soporte_liquidacion  INTEGER NOT NULL DEFAULT 0,
    fecha_soporte        TEXT,
    verificada_pago      TEXT,
    fecha_envio_gd       TEXT,
    clinicos_destruidos  TEXT,
    usuario              TEXT
);

CREATE TABLE IF NOT EXISTS notificaciones (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    incapacidad_id INTEGER REFERENCES incapacidades(id),
    categoria      TEXT NOT NULL,
    destinatario_tipo TEXT,
    destinatario   TEXT,
    correo         TEXT,
    asunto         TEXT NOT NULL,
    mensaje        TEXT NOT NULL,
    estado         TEXT NOT NULL DEFAULT 'Pendiente',
    creado_en      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    enviado_en     TEXT,
    usuario        TEXT
);

CREATE TABLE IF NOT EXISTS auditoria (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    usuario    TEXT,
    rol        TEXT,
    accion     TEXT NOT NULL,
    entidad    TEXT,
    entidad_id INTEGER,
    detalle    TEXT
);

CREATE INDEX IF NOT EXISTS idx_inc_estado ON incapacidades(estado);
CREATE INDEX IF NOT EXISTS idx_inc_colab  ON incapacidades(colaborador_id);
CREATE INDEX IF NOT EXISTS idx_hist_inc   ON historial_estados(incapacidad_id);
CREATE INDEX IF NOT EXISTS idx_gest_inc   ON gestiones_cobro(incapacidad_id);
"""
