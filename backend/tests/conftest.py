"""
Fixtures de pytest para el backend de Mision Atabey.

Proporciona:
  - mock_db   : reemplaza las funciones de DB con mocks (unittest.mock)
  - mock_mqtt : evita la conexion real al broker MQTT
  - client    : TestClient de FastAPI con DB y MQTT mockeados
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def require_login_by_default():
    """
    Fija REQUIRE_LOGIN=True para toda la suite.

    El modo de acceso viene de `backend/.env` (que en desarrollo puede estar
    en `false` para el dashboard publico). Sin este fixture los tests
    dependerian del entorno local. Los tests del modo anonimo lo patean
    explicitamente a `False`.
    """
    with (
        patch("backend.auth.REQUIRE_LOGIN", True),
        patch("backend.main.REQUIRE_LOGIN", True),
        patch("backend.auth.DEFAULT_ROL", "administrador"),
    ):
        yield


@pytest.fixture
def mock_db():
    """
    Reemplaza create_table, insert_reading, get_latest_reading, get_threshold,
    get_active_alerts, get_active_alert, get_alert_by_id y get_latest_location con mocks.
    """
    with (
        patch("backend.db.create_table"),
        patch("backend.db.insert_reading") as mock_insert,
        patch("backend.db.get_latest_reading") as mock_get,
        patch("backend.db.get_threshold", return_value=None) as mock_threshold,
        patch("backend.db.get_active_alerts", return_value=[]) as mock_alerts,
        patch("backend.db.get_active_alert", return_value=None) as mock_active_alert,
        patch("backend.db.get_alert_by_id", return_value=None) as mock_alert_by_id,
        patch("backend.db.get_latest_location", return_value=None) as mock_location,
        patch("backend.db.insert_ingest_ack", return_value={}) as mock_insert_ack,
        patch("backend.db.get_ingest_acks", return_value=[]) as mock_get_acks,
        patch("backend.db.insert_audit_log", return_value={}) as mock_insert_audit,
        patch("backend.db.get_audit_log", return_value=[]) as mock_get_audit,
    ):
        yield {
            "insert": mock_insert,
            "get": mock_get,
            "threshold": mock_threshold,
            "alerts": mock_alerts,
            "active_alert": mock_active_alert,
            "alert_by_id": mock_alert_by_id,
            "location": mock_location,
            "insert_ack": mock_insert_ack,
            "get_acks": mock_get_acks,
            "insert_audit": mock_insert_audit,
            "get_audit": mock_get_audit,
        }


@pytest.fixture
def mock_mqtt():
    """Evita la conexion real al broker MQTT durante los tests."""
    with (
        patch("backend.mqtt_client.start"),
        patch("backend.mqtt_client.stop"),
    ):
        yield


@pytest.fixture
def client(mock_db, mock_mqtt):
    """
    TestClient de FastAPI completamente aislado (sin BD real, sin MQTT real).
    Depende de mock_db y mock_mqtt para garantizar el aislamiento.
    """
    from backend.main import app

    with TestClient(app) as c:
        yield c
