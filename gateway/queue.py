"""
Cola offline SQLite para el gateway de Mision Atabey.

Toda lectura entra primero aqui, haya o no conexion al broker remoto.
La tabla `queue` es persistente en disco y sirve como buffer de durabilidad.

Esquema de la tabla:
    id          INTEGER  PRIMARY KEY AUTOINCREMENT
    sensor_id   TEXT     NOT NULL
    sequence    INTEGER  NOT NULL
    payload     TEXT     NOT NULL   -- JSON completo del contrato de datos
    synced      INTEGER  NOT NULL DEFAULT 0  -- 0=pendiente, 1=enviado

Un indice UNIQUE en (sensor_id, sequence) garantiza que un reinicio del
proceso no reencole duplicados: enqueue() hace INSERT OR IGNORE.
"""

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).parent / "gateway_queue.db"


class OfflineQueue:
    """
    Cola de lecturas pendientes de sincronizar, respaldada en SQLite.

    Thread-safe: sincroniza todos los accesos a la conexion SQLite
    mediante threading.RLock, permitiendo ejecucion concurrente segura
    desde multiples orquestadores (domo, EVA) y el hilo de sync.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._lock = threading.RLock()
        with self._lock:
            self._conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                isolation_level=None,  # autocommit; usamos transacciones explicitas
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._create_table()
        logger.info("Cola SQLite inicializada en %s", self.db_path)

    # ------------------------------------------------------------------
    # DDL
    # ------------------------------------------------------------------

    def _create_table(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS queue (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    sensor_id TEXT    NOT NULL,
                    sequence  INTEGER NOT NULL,
                    payload   TEXT    NOT NULL,
                    synced    INTEGER NOT NULL DEFAULT 0,
                    UNIQUE (sensor_id, sequence)
                )
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_queue_pending
                    ON queue (synced, sensor_id, sequence)
                """
            )

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------

    def enqueue(self, reading: dict) -> None:
        """
        Inserta una lectura en la cola.

        Usa INSERT OR IGNORE para ser idempotente: si el par
        (sensor_id, sequence) ya existe (p. ej. tras un reinicio), no
        se crea un duplicado.
        """
        payload_json = json.dumps(reading, default=str)
        with self._lock:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO queue (sensor_id, sequence, payload, synced)
                VALUES (?, ?, ?, 0)
                """,
                (reading["sensor_id"], reading["sequence"], payload_json),
            )
        logger.debug(
            "Encolado: sensor=%s seq=%d", reading["sensor_id"], reading["sequence"]
        )

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------

    def pending(self, limit: int = 50) -> list[dict]:
        """
        Devuelve hasta `limit` lecturas pendientes (synced=0) ordenadas
        por (sensor_id, sequence) para garantizar orden de entrega.
        """
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT id, payload
                FROM queue
                WHERE synced = 0
                ORDER BY sensor_id, sequence
                LIMIT ?
                """,
                (limit,),
            )
            rows = cur.fetchall()
        return [{"_row_id": row[0], **json.loads(row[1])} for row in rows]

    def mark_synced(self, row_id: int) -> None:
        """Marca una fila como sincronizada."""
        with self._lock:
            self._conn.execute(
                "UPDATE queue SET synced = 1 WHERE id = ?", (row_id,)
            )
        logger.debug("Marcado synced: row_id=%d", row_id)

    # ------------------------------------------------------------------
    # Introspección (util para pruebas y README manual)
    # ------------------------------------------------------------------

    def count_pending(self) -> int:
        with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) FROM queue WHERE synced = 0")
            row = cur.fetchone()
            return row[0] if row is not None else 0

    def count_total(self) -> int:
        with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) FROM queue")
            row = cur.fetchone()
            return row[0] if row is not None else 0

    # ------------------------------------------------------------------
    # Cierre
    # ------------------------------------------------------------------

    def close(self) -> None:
        with self._lock:
            self._conn.close()
            logger.info("Cola SQLite cerrada.")
