"""
Capa de acceso a datos — PostgreSQL via psycopg2.

Funciones disponibles:
    create_table()                              — crea todas las tablas, seeds
    insert_reading(reading, buffer_id=None)      — inserta una SensorReading
    insert_reading_batch(readings, buffer_id)    — inserta un buffer completo (transaccion)
    get_recent_ingest(limit)                     — registro de ingesta (cuando se guardo, de que sensor)
    get_buffer_readings(buffer_id)               — lecturas ya guardadas de un buffer
    get_latest_reading(sensor_id)               — ultima lectura por sensor_id
    get_user_by_username(username)              — usuario por nombre o None
    get_all_users()                             — lista de todos los usuarios (sin hash)
    create_user(username, password_hash, rol)   — inserta un usuario nuevo
    delete_user(user_id)                        — elimina un usuario por id
    get_threshold(sensor_id)                    — umbral de un sensor o None
    get_all_thresholds()                        — todos los umbrales
    upsert_threshold(sensor_id, min, max, user) — crea o actualiza umbral
    get_active_alert(sensor_id, excedido)       — alerta activa para sensor+direccion o None
    insert_alert(...)                           — crea alerta nueva
    update_alert_value(id, value, ts)           — actualiza value y visto_por_ultima_vez
    resolve_alert(id, resuelto_por)             — marca alerta como resuelta
    get_active_alerts()                         — alertas no resueltas
    insert_location(location)                   — inserta un LocationUpdate
    get_latest_location(device_id)              — ultima posicion de un device_id o None
    get_tripulantes_meta()                      — metadata (sexo) por device_id
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras
from psycopg2.extras import execute_values
from dotenv import load_dotenv

from backend.models import LocationUpdate, SensorReading

load_dotenv(Path(__file__).parent / ".env")

logger = logging.getLogger(__name__)

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://atabey:atabey@localhost:5433/atabey",
)

ROLES_VALIDOS = {"administrador", "control_mision", "observador"}

# Umbrales semilla — siempre en BD, nunca hardcodeados en logica de negocio
_THRESHOLD_SEEDS = [
    # (sensor_id,          valor_min, valor_max)
    ("EVA-TEMP-01",        13.0,      37.0),   # traje EVA: rango seguro de temperatura
    ("BTEMP-01",           36.0,      38.5),   # temperatura corporal normal
    ("HR-01",              40.0,     180.0),   # pulso cardiaco
    ("SPO2-01",            90.0,     100.0),   # saturacion de oxigeno (%)
    ("TEMP-01",           -10.0,      50.0),   # temperatura ambiente domo
    ("HUM-01",              0.0,     100.0),   # humedad relativa (%)
    ("CO2-01",              0.0,    5000.0),   # CO2 en ppm
    ("LUX-01",              0.0,   80000.0),   # iluminacion en lux
    ("SOIL-HUM-01",         0.0,     100.0),   # humedad de suelo (%)
    ("EVA-HUM-01",          0.0,     100.0),   # humedad relativa traje
    ("EVA-PRESS-01",      950.0,    1050.0),   # presion atmosferica (hPa)
]


def get_connection():
    """Abre y devuelve una nueva conexion a PostgreSQL."""
    return psycopg2.connect(DATABASE_URL)


def create_table() -> None:
    """Crea todas las tablas si no existen y genera los datos semilla."""
    sql_readings = """
        CREATE TABLE IF NOT EXISTS readings (
            id         SERIAL PRIMARY KEY,
            device_id  TEXT             NOT NULL,
            sensor_id  TEXT             NOT NULL,
            timestamp  TIMESTAMPTZ      NOT NULL,
            value      DOUBLE PRECISION NOT NULL,
            unit       TEXT             NOT NULL,
            sequence   INTEGER          NOT NULL,
            received_at TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            buffer_id  TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_readings_sensor_ts
            ON readings (sensor_id, timestamp DESC);
    """
    # Migracion: columnas de auditoria de ingesta (cuando se guardo, de que
    # envio/buffer vino). No alteran el contrato de la lectura.
    sql_migrate_readings_ingest = """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='readings' AND column_name='received_at'
            ) THEN
                ALTER TABLE readings
                    ADD COLUMN received_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='readings' AND column_name='buffer_id'
            ) THEN
                ALTER TABLE readings ADD COLUMN buffer_id TEXT;
            END IF;
        END$$;
    """
    sql_users = """
        CREATE TABLE IF NOT EXISTS users (
            id            SERIAL PRIMARY KEY,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            rol           TEXT NOT NULL DEFAULT 'observador'
        );
    """
    sql_migrate_role = """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='role'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='rol'
            ) THEN
                ALTER TABLE users RENAME COLUMN "role" TO rol;
            END IF;
        END$$;
    """
    sql_thresholds = """
        CREATE TABLE IF NOT EXISTS thresholds (
            sensor_id       TEXT PRIMARY KEY,
            valor_min       DOUBLE PRECISION NOT NULL,
            valor_max       DOUBLE PRECISION NOT NULL,
            actualizado_por TEXT,
            actualizado_en  TIMESTAMPTZ DEFAULT now()
        );
    """
    sql_alerts = """
        CREATE TABLE IF NOT EXISTS alerts (
            id                    SERIAL PRIMARY KEY,
            sensor_id             TEXT             NOT NULL,
            value                 DOUBLE PRECISION NOT NULL,
            threshold_excedido    TEXT             NOT NULL CHECK (threshold_excedido IN ('min','max')),
            valor_min             DOUBLE PRECISION NOT NULL,
            valor_max             DOUBLE PRECISION NOT NULL,
            timestamp             TIMESTAMPTZ      NOT NULL,
            severidad             TEXT             NOT NULL,
            resuelto              BOOLEAN          NOT NULL DEFAULT FALSE,
            visto_por_ultima_vez  TIMESTAMPTZ,
            resuelto_en           TIMESTAMPTZ,
            resuelto_por          TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_alerts_sensor_ts
            ON alerts (sensor_id, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_alerts_resuelto
            ON alerts (resuelto) WHERE resuelto = FALSE;
        CREATE INDEX IF NOT EXISTS idx_alerts_active_sensor
            ON alerts (sensor_id, threshold_excedido) WHERE resuelto = FALSE;
    """
    # Migracion: agrega columnas nuevas si la tabla ya existia sin ellas
    sql_migrate_alerts = """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='alerts' AND column_name='visto_por_ultima_vez'
            ) THEN
                ALTER TABLE alerts ADD COLUMN visto_por_ultima_vez TIMESTAMPTZ;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='alerts' AND column_name='resuelto_en'
            ) THEN
                ALTER TABLE alerts ADD COLUMN resuelto_en TIMESTAMPTZ;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='alerts' AND column_name='resuelto_por'
            ) THEN
                ALTER TABLE alerts ADD COLUMN resuelto_por TEXT;
            END IF;
        END$$;
    """
    # Migracion: normalizar valores de rol con mayusculas de versiones anteriores
    sql_migrate_rol_values = """
        UPDATE users SET rol = 'administrador'  WHERE lower(rol) = 'administrador'  AND rol != 'administrador';
        UPDATE users SET rol = 'control_mision' WHERE lower(rol) = 'control_mision' AND rol != 'control_mision';
        UPDATE users SET rol = 'observador'     WHERE lower(rol) = 'observador'     AND rol != 'observador';
    """
    # Migracion: agrega CHECK constraint en rol si no existe aun
    sql_migrate_rol_check = """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'users'
                  AND constraint_name = 'users_rol_check'
            ) THEN
                ALTER TABLE users
                    ADD CONSTRAINT users_rol_check
                    CHECK (rol IN ('administrador', 'control_mision', 'observador'));
            END IF;
        END$$;
    """
    sql_locations = """
        CREATE TABLE IF NOT EXISTS locations (
            id         SERIAL PRIMARY KEY,
            device_id  TEXT             NOT NULL,
            timestamp  TIMESTAMPTZ      NOT NULL,
            lat        DOUBLE PRECISION NOT NULL,
            lon        DOUBLE PRECISION NOT NULL,
            sequence   INTEGER          NOT NULL,
            sexo       TEXT             CHECK (sexo IS NULL OR sexo IN ('M','F'))
        );
        CREATE INDEX IF NOT EXISTS idx_locations_device_ts
            ON locations (device_id, timestamp DESC);
    """
    # Migracion: agrega columna sexo si la tabla ya existia sin ella
    sql_migrate_locations_sexo = """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='locations' AND column_name='sexo'
            ) THEN
                ALTER TABLE locations
                    ADD COLUMN sexo TEXT CHECK (sexo IS NULL OR sexo IN ('M','F'));
            END IF;
        END$$;
    """
    # Tablas de auditoría (Prompt 14): historico de ACKs y cambios de configuracion
    sql_ingest_ack_audit = """
        CREATE TABLE IF NOT EXISTS ingest_ack_audit (
            id          SERIAL PRIMARY KEY,
            device_id   TEXT             NOT NULL,
            buffer_id   TEXT             NOT NULL UNIQUE,
            received_at TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
            total_items INTEGER          NOT NULL,
            accepted    INTEGER          NOT NULL,
            rejected    INTEGER          NOT NULL,
            duplicates  INTEGER          NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ingest_ack_device_ts
            ON ingest_ack_audit (device_id, received_at DESC);
    """
    sql_audit_log = """
        CREATE TABLE IF NOT EXISTS audit_log (
            id          SERIAL PRIMARY KEY,
            entity      TEXT             NOT NULL,
            action      TEXT             NOT NULL,
            entity_id   TEXT             NOT NULL,
            old_value   TEXT,
            new_value   TEXT,
            changed_by  TEXT,
            changed_at  TIMESTAMPTZ      NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_audit_log_entity_ts
            ON audit_log (entity, changed_at DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_log_entity_id
            ON audit_log (entity_id);
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_readings)
            cur.execute(sql_users)
            cur.execute(sql_migrate_role)
            cur.execute(sql_thresholds)
            cur.execute(sql_alerts)
            cur.execute(sql_migrate_alerts)
            cur.execute(sql_migrate_rol_values)
            cur.execute(sql_migrate_rol_check)
            cur.execute(sql_locations)
            cur.execute(sql_migrate_locations_sexo)
            cur.execute(sql_migrate_readings_ingest)
            cur.execute(sql_ingest_ack_audit)
            cur.execute(sql_audit_log)
        conn.commit()
    logger.info("Tablas verificadas/creadas.")

    _seed_users()
    _seed_thresholds()


def _seed_users() -> None:
    """Inserta los tres usuarios de prueba si no existen."""
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    seeds = [
        (
            os.getenv("SEED_ADMIN_USER", "admin"),
            os.getenv("SEED_ADMIN_PASSWORD", "admin_pass"),
            "administrador",
        ),
        ("mision", "mision_pass", "control_mision"),
        ("observador", "observador_pass", "observador"),
    ]
    with get_connection() as conn:
        with conn.cursor() as cur:
            for username, password, rol in seeds:
                cur.execute("SELECT id FROM users WHERE username = %s", (username,))
                if cur.fetchone() is None:
                    p_hash = pwd_context.hash(password)
                    cur.execute(
                        "INSERT INTO users (username, password_hash, rol) VALUES (%s, %s, %s)",
                        (username, p_hash, rol),
                    )
                    logger.info("Usuario semilla '%s' (%s) creado.", username, rol)
        conn.commit()


def _seed_thresholds() -> None:
    """Inserta los umbrales semilla si no existen ya para ese sensor_id."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            for sensor_id, valor_min, valor_max in _THRESHOLD_SEEDS:
                cur.execute(
                    "SELECT sensor_id FROM thresholds WHERE sensor_id = %s",
                    (sensor_id,),
                )
                if cur.fetchone() is None:
                    cur.execute(
                        """INSERT INTO thresholds (sensor_id, valor_min, valor_max, actualizado_por)
                           VALUES (%s, %s, %s, 'seed')""",
                        (sensor_id, valor_min, valor_max),
                    )
                    logger.info(
                        "Umbral semilla '%s': [%.1f, %.1f]", sensor_id, valor_min, valor_max
                    )
        conn.commit()


# ── Readings ──────────────────────────────────────────────────────────────────

def insert_reading(reading: SensorReading, buffer_id: Optional[str] = None) -> dict:
    """
    Inserta una lectura en la tabla readings y devuelve el registro guardado
    (incluye `received_at`: el momento en que el servidor la guardo).
    """
    sql = """
        INSERT INTO readings (device_id, sensor_id, timestamp, value, unit, sequence, buffer_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id, device_id, sensor_id, timestamp, value, unit, sequence,
                  received_at, buffer_id
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                sql,
                (
                    reading.device_id,
                    reading.sensor_id,
                    reading.timestamp,
                    reading.value,
                    reading.unit,
                    reading.sequence,
                    buffer_id,
                ),
            )
            row = cur.fetchone()
        conn.commit()
    logger.debug("Lectura insertada: %s seq=%d", reading.sensor_id, reading.sequence)
    return dict(row)


def insert_reading_batch(readings: list, buffer_id: Optional[str] = None) -> list[dict]:
    """
    Inserta un buffer de lecturas completo en UNA transaccion.

    Devuelve la lista de registros guardados (con `received_at` y `db_id`).
    Si algo falla, no se guarda ninguna (todo o nada) — el ESP32 reintentaria
    el buffer completo.
    """
    if not readings:
        return []
    sql = """
        INSERT INTO readings (device_id, sensor_id, timestamp, value, unit, sequence, buffer_id)
        VALUES %s
        RETURNING id, device_id, sensor_id, timestamp, value, unit, sequence,
                  received_at, buffer_id
    """
    values = [
        (
            r.device_id,
            r.sensor_id,
            r.timestamp,
            r.value,
            r.unit,
            r.sequence,
            buffer_id,
        )
        for r in readings
    ]
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # execute_values construye el VALUES multi-fila; con `cur.execute`
            # psycopg2 no acepta una lista de tuplas como un solo parametro.
            execute_values(cur, sql, values)
            rows = cur.fetchall()
        conn.commit()
    logger.info("Buffer %s guardado: %d lecturas", buffer_id, len(rows))
    return [dict(r) for r in rows]


def get_recent_ingest(limit: int = 100) -> list[dict]:
    """
    Devuelve el registro de ingesta: que se guardo, de que sensor vino,
    cuando lo midio el sensor y cuando lo guardo el servidor.
    """
    sql = """
        SELECT id, device_id, sensor_id, value, unit, timestamp,
               received_at, buffer_id, sequence
        FROM readings
        ORDER BY received_at DESC, id DESC
        LIMIT %s
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_buffer_readings(buffer_id: str) -> list[dict]:
    """Devuelve las lecturas ya guardadas de un buffer (para idempotencia)."""
    sql = """
        SELECT id, device_id, sensor_id, timestamp, value, unit, sequence,
               received_at, buffer_id
        FROM readings
        WHERE buffer_id = %s
        ORDER BY id ASC
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (buffer_id,))
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_latest_reading(sensor_id: str) -> Optional[dict]:
    """Devuelve la lectura mas reciente para sensor_id, o None si no hay datos."""
    sql = """
        SELECT device_id, sensor_id, timestamp, value, unit, sequence
        FROM readings
        WHERE sensor_id = %s
        ORDER BY timestamp DESC
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (sensor_id,))
            row = cur.fetchone()
    return dict(row) if row else None


# ── Users ─────────────────────────────────────────────────────────────────────

def get_user_by_username(username: str) -> Optional[dict]:
    sql = "SELECT id, username, password_hash, rol FROM users WHERE username = %s"
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (username,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_all_users() -> list:
    """Devuelve todos los usuarios (sin password_hash)."""
    sql = "SELECT id, username, rol FROM users ORDER BY id"
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def create_user(username: str, password_hash: str, rol: str) -> dict:
    """Crea un usuario nuevo y devuelve su representacion (sin hash)."""
    if rol not in ROLES_VALIDOS:
        raise ValueError(f"Rol invalido: {rol!r}. Debe ser uno de {ROLES_VALIDOS}.")
    sql = """
        INSERT INTO users (username, password_hash, rol)
        VALUES (%s, %s, %s)
        RETURNING id, username, rol
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (username, password_hash, rol))
            row = cur.fetchone()
        conn.commit()
    return dict(row)


def delete_user(user_id: int) -> bool:
    """Elimina un usuario por id. Devuelve True si existia."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            deleted = cur.rowcount > 0
        conn.commit()
    return deleted


# ── Thresholds ────────────────────────────────────────────────────────────────

def get_threshold(sensor_id: str) -> Optional[dict]:
    """Devuelve el umbral de un sensor, o None si no esta configurado."""
    sql = """
        SELECT sensor_id, valor_min, valor_max, actualizado_por, actualizado_en
        FROM thresholds
        WHERE sensor_id = %s
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (sensor_id,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_all_thresholds() -> list:
    """Devuelve todos los umbrales configurados."""
    sql = "SELECT sensor_id, valor_min, valor_max, actualizado_por, actualizado_en FROM thresholds ORDER BY sensor_id"
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def upsert_threshold(
    sensor_id: str,
    valor_min: float,
    valor_max: float,
    actualizado_por: str,
) -> dict:
    """Crea o actualiza el umbral para sensor_id. Devuelve el registro resultante."""
    sql = """
        INSERT INTO thresholds (sensor_id, valor_min, valor_max, actualizado_por, actualizado_en)
        VALUES (%s, %s, %s, %s, now())
        ON CONFLICT (sensor_id) DO UPDATE
            SET valor_min       = EXCLUDED.valor_min,
                valor_max       = EXCLUDED.valor_max,
                actualizado_por = EXCLUDED.actualizado_por,
                actualizado_en  = now()
        RETURNING sensor_id, valor_min, valor_max, actualizado_por, actualizado_en
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (sensor_id, valor_min, valor_max, actualizado_por))
            row = cur.fetchone()
        conn.commit()
    return dict(row)


# ── Alerts ────────────────────────────────────────────────────────────────────

def get_active_alert(sensor_id: str, threshold_excedido: str) -> Optional[dict]:
    """
    Devuelve la alerta activa (resuelto=false) para sensor_id en la direccion
    indicada ('min' o 'max'), o None si no existe ninguna.
    """
    sql = """
        SELECT id, sensor_id, value, threshold_excedido, valor_min, valor_max,
               timestamp, severidad, resuelto, visto_por_ultima_vez,
               resuelto_en, resuelto_por
        FROM alerts
        WHERE sensor_id = %s
          AND threshold_excedido = %s
          AND resuelto = FALSE
        ORDER BY timestamp DESC
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (sensor_id, threshold_excedido))
            row = cur.fetchone()
    return dict(row) if row else None


def insert_alert(
    sensor_id: str,
    value: float,
    threshold_excedido: str,   # "min" | "max"
    valor_min: float,
    valor_max: float,
    timestamp: datetime,
    severidad: str,
) -> dict:
    """Crea un registro de alerta nuevo y lo devuelve."""
    sql = """
        INSERT INTO alerts
            (sensor_id, value, threshold_excedido, valor_min, valor_max,
             timestamp, severidad, visto_por_ultima_vez)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, sensor_id, value, threshold_excedido, valor_min, valor_max,
                  timestamp, severidad, resuelto, visto_por_ultima_vez,
                  resuelto_en, resuelto_por
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                sql,
                (sensor_id, value, threshold_excedido, valor_min, valor_max,
                 timestamp, severidad, timestamp),
            )
            row = cur.fetchone()
        conn.commit()
    logger.warning(
        "ALERTA NUEVA [%s] %s = %.2f fuera de rango [%.2f, %.2f] (severidad=%s)",
        sensor_id, threshold_excedido, value, valor_min, valor_max, severidad,
    )
    return dict(row)


def update_alert_value(alert_id: int, value: float, timestamp: datetime) -> dict:
    """
    Actualiza el value y visto_por_ultima_vez de una alerta activa existente.
    No crea una fila nueva — deduplicacion de lecturas consecutivas fuera de rango.
    """
    sql = """
        UPDATE alerts
        SET value = %s,
            visto_por_ultima_vez = %s
        WHERE id = %s
        RETURNING id, sensor_id, value, threshold_excedido, valor_min, valor_max,
                  timestamp, severidad, resuelto, visto_por_ultima_vez,
                  resuelto_en, resuelto_por
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (value, timestamp, alert_id))
            row = cur.fetchone()
        conn.commit()
    logger.debug("Alerta %d actualizada: value=%.2f visto_en=%s", alert_id, value, timestamp)
    return dict(row)


def resolve_alert(alert_id: int, resuelto_por: Optional[str] = None) -> Optional[dict]:
    """
    Marca una alerta como resuelta. Devuelve el registro actualizado, o None si no existe.
    resuelto_por=None indica resolucion automatica (lectura volvio al rango).
    """
    sql = """
        UPDATE alerts
        SET resuelto    = TRUE,
            resuelto_en = now(),
            resuelto_por = %s
        WHERE id = %s AND resuelto = FALSE
        RETURNING id, sensor_id, value, threshold_excedido, valor_min, valor_max,
                  timestamp, severidad, resuelto, visto_por_ultima_vez,
                  resuelto_en, resuelto_por
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (resuelto_por, alert_id))
            row = cur.fetchone()
        conn.commit()
    if row:
        logger.info(
            "Alerta %d resuelta (resuelto_por=%r)", alert_id, resuelto_por
        )
    return dict(row) if row else None


def get_active_alerts() -> list:
    """Devuelve todas las alertas no resueltas, mas recientes primero."""
    sql = """
        SELECT id, sensor_id, value, threshold_excedido, valor_min, valor_max,
               timestamp, severidad, resuelto, visto_por_ultima_vez,
               resuelto_en, resuelto_por
        FROM alerts
        WHERE resuelto = FALSE
        ORDER BY timestamp DESC
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_alert_by_id(alert_id: int) -> Optional[dict]:
    """Devuelve una alerta por id, o None si no existe."""
    sql = """
        SELECT id, sensor_id, value, threshold_excedido, valor_min, valor_max,
               timestamp, severidad, resuelto, visto_por_ultima_vez,
               resuelto_en, resuelto_por
        FROM alerts WHERE id = %s
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (alert_id,))
            row = cur.fetchone()
    return dict(row) if row else None


# ── Locations ─────────────────────────────────────────────────────────────────

def insert_location(location: LocationUpdate) -> dict:
    """Inserta una actualizacion de posicion y devuelve el registro creado."""
    sql = """
        INSERT INTO locations (device_id, timestamp, lat, lon, sequence, sexo)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, device_id, timestamp, lat, lon, sequence, sexo
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                sql,
                (location.device_id, location.timestamp,
                 location.lat, location.lon, location.sequence,
                 getattr(location, "sexo", None)))
            row = cur.fetchone()
        conn.commit()
    logger.debug("Posicion insertada: %s seq=%d (%.6f, %.6f)",
                 location.device_id, location.sequence, location.lat, location.lon)
    return dict(row)


def get_latest_location(device_id: str) -> Optional[dict]:
    """Devuelve la posicion mas reciente de un device_id, o None si no hay datos."""
    sql = """
        SELECT id, device_id, timestamp, lat, lon, sequence, sexo
        FROM locations
        WHERE device_id = %s
        ORDER BY timestamp DESC
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (device_id,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_tripulantes_meta() -> list:
    """
    Devuelve la metadata de cada tripulante conocido (un registro por device_id,
    tomando el sexo mas reciente no nulo). Se usa unicamente para el color del
    marcador en el mapa — no filtra ni restringe acceso.
    """
    sql = """
        SELECT device_id,
               (SELECT sexo
                  FROM locations l2
                 WHERE l2.device_id = l1.device_id
                   AND l2.sexo IS NOT NULL
                 ORDER BY l2.timestamp DESC
                 LIMIT 1) AS sexo
        FROM locations l1
        GROUP BY device_id
        ORDER BY device_id
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    return [dict(r) for r in rows]


# ── Auditoría: ACK de Buffers ─────────────────────────────────────────────────

def insert_ingest_ack(
    device_id: str,
    buffer_id: str,
    total_items: int,
    accepted: int,
    rejected: int,
    duplicates: int,
) -> dict:
    """
    Registra un ACK de ingesta en la tabla de auditoría.
    Se llama desde mqtt_client.ingest_batch() tras procesar un buffer exitosamente.
    """
    sql = """
        INSERT INTO ingest_ack_audit (device_id, buffer_id, total_items, accepted, rejected, duplicates)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, device_id, buffer_id, received_at, total_items, accepted, rejected, duplicates
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (device_id, buffer_id, total_items, accepted, rejected, duplicates))
            row = cur.fetchone()
        conn.commit()
    logger.info("ACK auditado: buffer_id=%s device_id=%s (aceptadas=%d duplicadas=%d rechazadas=%d)",
                buffer_id, device_id, accepted, duplicates, rejected)
    return dict(row) if row else {}


def get_ingest_acks(device_id: Optional[str] = None, limit: int = 100) -> list:
    """
    Devuelve el histórico de ACKs de buffers (últimos `limit`).
    Si device_id es especificado, filtra solo para ese dispositivo.
    """
    if device_id:
        sql = """
            SELECT id, device_id, buffer_id, received_at, total_items, accepted, rejected, duplicates
            FROM ingest_ack_audit
            WHERE device_id = %s
            ORDER BY received_at DESC
            LIMIT %s
        """
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (device_id, limit))
                rows = cur.fetchall()
    else:
        sql = """
            SELECT id, device_id, buffer_id, received_at, total_items, accepted, rejected, duplicates
            FROM ingest_ack_audit
            ORDER BY received_at DESC
            LIMIT %s
        """
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (limit,))
                rows = cur.fetchall()
    return [dict(r) for r in rows]


# ── Auditoría: Cambios de Configuración ──────────────────────────────────────

def insert_audit_log(
    entity: str,
    action: str,
    entity_id: str,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    changed_by: Optional[str] = None,
) -> dict:
    """
    Registra un cambio en la tabla de auditoría.
    
    entity: 'umbral', 'alerta', 'usuario', etc.
    action: 'create', 'update', 'delete', 'resolve', etc.
    entity_id: identificador de la entidad (sensor_id, alert_id, user_id, etc.)
    old_value: valor anterior (JSON serializado si es un objeto)
    new_value: valor nuevo (JSON serializado si es un objeto)
    changed_by: usuario que realizó el cambio
    """
    sql = """
        INSERT INTO audit_log (entity, action, entity_id, old_value, new_value, changed_by)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, entity, action, entity_id, old_value, new_value, changed_by, changed_at
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (entity, action, entity_id, old_value, new_value, changed_by))
            row = cur.fetchone()
        conn.commit()
    logger.info("Auditoría registrada: %s %s %s (changed_by=%s)", entity, action, entity_id, changed_by)
    return dict(row) if row else {}


def get_audit_log(
    entity: Optional[str] = None,
    entity_id: Optional[str] = None,
    limit: int = 100,
) -> list:
    """
    Devuelve el histórico de auditoría (últimos `limit` cambios).
    Si entity es especificado, filtra solo cambios de ese tipo de entidad.
    Si entity_id es especificado, filtra solo cambios a esa entidad.
    """
    if entity and entity_id:
        sql = """
            SELECT id, entity, action, entity_id, old_value, new_value, changed_by, changed_at
            FROM audit_log
            WHERE entity = %s AND entity_id = %s
            ORDER BY changed_at DESC
            LIMIT %s
        """
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (entity, entity_id, limit))
                rows = cur.fetchall()
    elif entity:
        sql = """
            SELECT id, entity, action, entity_id, old_value, new_value, changed_by, changed_at
            FROM audit_log
            WHERE entity = %s
            ORDER BY changed_at DESC
            LIMIT %s
        """
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (entity, limit))
                rows = cur.fetchall()
    else:
        sql = """
            SELECT id, entity, action, entity_id, old_value, new_value, changed_by, changed_at
            FROM audit_log
            ORDER BY changed_at DESC
            LIMIT %s
        """
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (limit,))
                rows = cur.fetchall()
    return [dict(r) for r in rows]
