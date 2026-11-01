"""
Tests del pipeline de telemetria — Modulo 1: temperatura del domo.

Cubren:
  (a) Un mensaje bien formado se guarda correctamente en la base de datos.
  (b) Un mensaje que no respeta el esquema se rechaza sin tumbar el backend.

Los tests usan mocks; no requieren Docker ni conexiones reales.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

import backend.mqtt_client as mqtt_client
from backend.models import SensorReading

# -- Payloads de prueba -------------------------------------------------------

VALID_PAYLOAD = {
    "device_id": "ESP32-01",
    "sensor_id": "TEMP-01",
    "timestamp": "2026-09-24T20:15:00Z",
    "value": 28.4,
    "unit": "C",
    "sequence": 1542,
}

PAYLOAD_MISSING_VALUE = {
    "device_id": "ESP32-01",
    "sensor_id": "TEMP-01",
    "timestamp": "2026-09-24T20:15:00Z",
    # "value" ausente
    "unit": "C",
    "sequence": 1542,
}

PAYLOAD_BAD_TYPES = {
    "device_id": "ESP32-01",
    "sensor_id": "TEMP-01",
    "timestamp": "not-a-date",
    "value": "not-a-float",
    "unit": "C",
    "sequence": "not-an-int",
}


# -- Tests del modelo Pydantic ------------------------------------------------

class TestSensorReadingModel:
    def test_valid_payload_se_parsea_correctamente(self):
        reading = SensorReading(**VALID_PAYLOAD)
        assert reading.device_id == "ESP32-01"
        assert reading.sensor_id == "TEMP-01"
        assert reading.value == 28.4
        assert reading.unit == "C"
        assert reading.sequence == 1542
        assert isinstance(reading.timestamp, datetime)

    def test_campo_ausente_lanza_validation_error(self):
        with pytest.raises(ValidationError):
            SensorReading(**PAYLOAD_MISSING_VALUE)

    def test_tipos_incorrectos_lanzan_validation_error(self):
        with pytest.raises(ValidationError):
            SensorReading(**PAYLOAD_BAD_TYPES)


# -- Tests del callback MQTT --------------------------------------------------

class TestMqttCallback:
    def _make_msg(self, payload: dict) -> MagicMock:
        """Crea un mensaje MQTT falso con el payload dado."""
        msg = MagicMock()
        msg.payload = json.dumps(payload).encode("utf-8")
        return msg

    def test_a_mensaje_valido_se_guarda_en_db(self):
        """(a) Un mensaje bien formado se guarda correctamente."""
        with patch("backend.mqtt_client.db.insert_reading") as mock_insert, \
             patch("backend.mqtt_client.db.get_threshold", return_value=None):
            mqtt_client.on_message(None, None, self._make_msg(VALID_PAYLOAD))

            mock_insert.assert_called_once()
            saved: SensorReading = mock_insert.call_args[0][0]
            assert isinstance(saved, SensorReading)
            assert saved.sensor_id == "TEMP-01"
            assert saved.value == 28.4
            assert saved.sequence == 1542

    def test_b_mensaje_campo_ausente_no_tumba_backend(self):
        """(b) Un mensaje con campo ausente se rechaza sin excepcion."""
        with patch("backend.mqtt_client.db.insert_reading") as mock_insert, \
             patch("backend.mqtt_client.db.get_threshold", return_value=None):
            # No debe lanzar ninguna excepcion
            mqtt_client.on_message(None, None, self._make_msg(PAYLOAD_MISSING_VALUE))

            # No se guarda nada
            mock_insert.assert_not_called()

    def test_b_mensaje_tipos_incorrectos_no_tumba_backend(self):
        """(b) Un mensaje con tipos incorrectos se rechaza sin excepcion."""
        with patch("backend.mqtt_client.db.insert_reading") as mock_insert, \
             patch("backend.mqtt_client.db.get_threshold", return_value=None):
            mqtt_client.on_message(None, None, self._make_msg(PAYLOAD_BAD_TYPES))
            mock_insert.assert_not_called()

    def test_b_json_malformado_no_tumba_backend(self):
        """(b) Payload que no es JSON valido se descarta sin excepcion."""
        with patch("backend.mqtt_client.db.insert_reading") as mock_insert, \
             patch("backend.mqtt_client.db.get_threshold", return_value=None):
            msg = MagicMock()
            msg.payload = b"esto no es json {"
            mqtt_client.on_message(None, None, msg)
            mock_insert.assert_not_called()

    def test_on_connect_se_suscribe_a_patron_wildcard(self):
        """Verifica que on_connect se suscribe al patron wildcard configurado."""
        mock_client = MagicMock()
        mock_reason = MagicMock()
        mock_reason.is_failure = False

        mqtt_client.on_connect(mock_client, None, None, mock_reason, None)

        mock_client.subscribe.assert_called_once_with(mqtt_client.TOPIC)
        assert mqtt_client.TOPIC.endswith("#") or mqtt_client.TOPIC.endswith("+")

    def test_procesa_mensajes_de_multiples_topicos_distintos(self):
        """
        Confirma que el backend procesa correctamente mensajes de al menos 3 topicos
        distintos con la suscripcion wildcard configurada (Domo y EVA).
        """
        mensajes_prueba = [
            (
                "atabey/domo/TEMP-01",
                {
                    "device_id": "ESP32-01",
                    "sensor_id": "TEMP-01",
                    "timestamp": "2026-09-24T20:15:00Z",
                    "value": 24.5,
                    "unit": "C",
                    "sequence": 1,
                },
            ),
            (
                "atabey/domo/HUM-01",
                {
                    "device_id": "ESP32-01",
                    "sensor_id": "HUM-01",
                    "timestamp": "2026-09-24T20:15:01Z",
                    "value": 65.2,
                    "unit": "%",
                    "sequence": 1,
                },
            ),
            (
                "atabey/domo/HR-01",
                {
                    "device_id": "EVA-01",
                    "sensor_id": "HR-01",
                    "timestamp": "2026-09-24T20:15:02Z",
                    "value": 78.0,
                    "unit": "bpm",
                    "sequence": 1,
                },
            ),
            (
                "atabey/domo/ACTIVITY-01",
                {
                    "device_id": "EVA-01",
                    "sensor_id": "ACTIVITY-01",
                    "timestamp": "2026-09-24T20:15:03Z",
                    "value": 2,
                    "unit": "código",
                    "sequence": 1,
                },
            ),
        ]

        with patch("backend.mqtt_client.db.insert_reading") as mock_insert, \
             patch("backend.mqtt_client.db.get_threshold", return_value=None):
            for topic, payload in mensajes_prueba:
                msg = MagicMock()
                msg.topic = topic
                msg.payload = json.dumps(payload).encode("utf-8")
                mqtt_client.on_message(None, None, msg)

            assert mock_insert.call_count == len(mensajes_prueba)
            guardados = [call[0][0].sensor_id for call in mock_insert.call_args_list]
            assert guardados == ["TEMP-01", "HUM-01", "HR-01", "ACTIVITY-01"]


# -- Tests del endpoint REST --------------------------------------------------

def _admin_token() -> str:
    """Token JWT de un administrador para usar en tests de API REST."""
    from backend.auth import create_access_token
    return create_access_token(data={"sub": "admin", "rol": "administrador"})


def _mock_admin_user():
    from passlib.context import CryptContext
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return {
        "id": 1,
        "username": "admin",
        "password_hash": ctx.hash("admin_pass"),
        "rol": "administrador",
    }


class TestApiEndpoint:
    def test_latest_reading_devuelve_datos(self, client, mock_db):
        """GET /readings/latest devuelve la ultima lectura cuando existe."""
        mock_db["get"].return_value = {
            "device_id": "ESP32-01",
            "sensor_id": "TEMP-01",
            "timestamp": datetime(2026, 9, 24, 20, 15, 0, tzinfo=timezone.utc),
            "value": 28.4,
            "unit": "C",
            "sequence": 1542,
        }
        with patch("backend.auth.get_user_by_username", return_value=_mock_admin_user()):
            response = client.get(
                "/readings/latest?sensor_id=TEMP-01",
                headers={"Authorization": f"Bearer {_admin_token()}"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["sensor_id"] == "TEMP-01"
        assert data["value"] == 28.4
        assert data["sequence"] == 1542

    def test_latest_reading_404_cuando_no_hay_datos(self, client, mock_db):
        """GET /readings/latest devuelve 404 si no hay lecturas para ese sensor."""
        mock_db["get"].return_value = None
        with patch("backend.auth.get_user_by_username", return_value=_mock_admin_user()):
            response = client.get(
                "/readings/latest?sensor_id=TEMP-01",
                headers={"Authorization": f"Bearer {_admin_token()}"},
            )
        assert response.status_code == 404

    def test_latest_reading_requiere_sensor_id(self, client, mock_db):
        """GET /readings/latest sin sensor_id devuelve 422 (Unprocessable Entity)."""
        with patch("backend.auth.get_user_by_username", return_value=_mock_admin_user()):
            response = client.get(
                "/readings/latest",
                headers={"Authorization": f"Bearer {_admin_token()}"},
            )
        assert response.status_code == 422

    def test_health_ok(self, client, mock_db):
        """GET /health devuelve 200."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
