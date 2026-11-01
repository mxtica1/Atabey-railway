"""
Fixtures compartidas para las pruebas del gateway.
"""

import tempfile
from pathlib import Path

import pytest

from gateway.queue import OfflineQueue


@pytest.fixture
def tmp_queue(tmp_path: Path) -> OfflineQueue:
    """Cola SQLite en un directorio temporal; se descarta al terminar el test."""
    db_file = tmp_path / "test_queue.db"
    q = OfflineQueue(db_path=db_file)
    yield q
    q.close()


def make_reading(sequence: int, sensor_id: str = "TEMP-01") -> dict:
    """Fabrica una lectura valida del contrato de datos."""
    return {
        "device_id": "ESP32-01",
        "sensor_id": sensor_id,
        "timestamp": f"2026-09-24T20:{sequence:02d}:00Z",
        "value": 25.0 + sequence * 0.1,
        "unit": "C",
        "sequence": sequence,
    }
