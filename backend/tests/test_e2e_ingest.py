"""
E2E test — flujo completo: simulador → buffer MQTT → ACK → BD → auditoría
"""

import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

import backend.db as db
import backend.mqtt_client as mqtt_client
from backend.main import app
from backend.models import ReadingBatch, SensorReading

client = TestClient(app)


def _reading(sensor_id="TEMP-01", value=28.4, sequence=1, device_id="ESP32-01"):
    """Factory para crear lecturas de prueba."""
    return {
        "device_id": device_id,
        "sensor_id": sensor_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "value": value,
        "unit": "C",
        "sequence": sequence,
    }


def _buffer(device_id="ESP32-01", readings_count=2):
    """Factory para crear buffers de prueba."""
    return {
        "device_id": device_id,
        "buffer_id": f"e2e-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "readings": [
            _reading(f"TEMP-{i:02d}", 25.0 + i, i)
            for i in range(1, readings_count + 1)
        ],
    }


class TestE2EIngest:
    """E2E tests del pipeline de ingesta completo."""
    
    def test_e2e_buffer_to_ack_to_audit(self):
        """
        Valida flujo completo:
        1. Simulador envía buffer por MQTT
        2. Backend procesa y crea ACK
        3. ACK se registra en ingest_ack_audit
        4. Lecturas se guardan en readings
        5. ACK se publica de vuelta por MQTT
        """
        buffer_data = _buffer(device_id="ESP32-01", readings_count=3)
        batch = ReadingBatch(**buffer_data)
        
        with (
            patch("backend.db.get_buffer_readings", return_value=[]),
            patch("backend.db.insert_reading_batch") as mock_insert,
            patch("backend.db.get_threshold", return_value=None),
            patch("backend.db.insert_ingest_ack") as mock_insert_ack,
            patch("backend.mqtt_client.publish_ack") as mock_publish_ack,
        ):
            # Simular guardado de lecturas
            mock_insert.side_effect = lambda readings, buffer_id=None: [
                {
                    "id": 100 + idx,
                    "device_id": r.device_id,
                    "sensor_id": r.sensor_id,
                    "timestamp": r.timestamp,
                    "value": r.value,
                    "unit": r.unit,
                    "sequence": r.sequence,
                    "received_at": datetime.now(timezone.utc),
                    "buffer_id": buffer_id,
                }
                for idx, r in enumerate(readings)
            ]
            
            # Ejecutar ingesta
            ack = mqtt_client.ingest_batch(batch)
            
            # Validar ACK retornado
            assert ack.buffer_id == buffer_data["buffer_id"]
            assert ack.accepted == 3
            assert ack.rejected == 0
            assert ack.duplicates == 0
            assert len(ack.items) == 3
            
            # Validar que se registró en auditoría
            mock_insert_ack.assert_called_once()
            audit_call = mock_insert_ack.call_args
            assert audit_call.kwargs["device_id"] == "ESP32-01"
            assert audit_call.kwargs["total_items"] == 3
            assert audit_call.kwargs["accepted"] == 3
            
            # Validar que ACK se retorna (publish_ack es llamado desde endpoint HTTP)
            # En este test mockeamos publish_ack, así que no se llama realmente
            # Pero en el endpoint HTTP sí se publica (ver test_e2e_http_endpoint_complete_flow)
    
    
    def test_e2e_idempotencia_sin_duplicados(self):
        """
        Valida que buffer reenviado:
        1. Se detecta como duplicate en auditoría
        2. No duplica lecturas en readings
        3. Retorna ACK con status "duplicate"
        """
        buffer_data = _buffer(device_id="ESP32-01", readings_count=2)
        batch = ReadingBatch(**buffer_data)
        
        # Simulamos que el buffer ya fue procesado
        existing_readings = [
            {
                "id": 100,
                "device_id": "ESP32-01",
                "sensor_id": "TEMP-01",
                "timestamp": datetime.now(timezone.utc),
                "value": 25.0,
                "unit": "C",
                "sequence": 1,
                "received_at": datetime.now(timezone.utc),
                "buffer_id": buffer_data["buffer_id"],
            },
            {
                "id": 101,
                "device_id": "ESP32-01",
                "sensor_id": "TEMP-02",
                "timestamp": datetime.now(timezone.utc),
                "value": 26.0,
                "unit": "C",
                "sequence": 2,
                "received_at": datetime.now(timezone.utc),
                "buffer_id": buffer_data["buffer_id"],
            },
        ]
        
        with (
            patch("backend.db.get_buffer_readings", return_value=existing_readings),
            patch("backend.db.insert_reading_batch") as mock_insert,
            patch("backend.db.insert_ingest_ack") as mock_insert_ack,
        ):
            ack = mqtt_client.ingest_batch(batch)
            
            # No debe insertar nada
            mock_insert.assert_not_called()
            
            # Validar ACK
            assert ack.duplicates == 2
            assert ack.accepted == 0
            assert all(item.status == "duplicate" for item in ack.items)
            assert ack.items[0].db_id == 100
            assert ack.items[1].db_id == 101
    
    
    def test_e2e_threshold_evaluation(self):
        """
        Valida que lectura fuera de umbral:
        1. Se guarda en readings
        2. Genera alerta
        3. Se registra en audit_log (cuando se resuelva)
        """
        buffer_data = _buffer(device_id="ESP32-01", readings_count=1)
        buffer_data["readings"][0]["value"] = 99.0  # Fuera de rango
        batch = ReadingBatch(**buffer_data)
        
        threshold = {"sensor_id": "TEMP-01", "valor_min": 15.0, "valor_max": 35.0}
        
        with (
            patch("backend.db.get_buffer_readings", return_value=[]),
            patch("backend.db.insert_reading_batch") as mock_insert,
            patch("backend.db.get_threshold", return_value=threshold),
            patch("backend.db.get_active_alert", return_value=None),
            patch("backend.db.insert_alert") as mock_insert_alert,
            patch("backend.db.insert_ingest_ack") as mock_insert_ack,
        ):
            mock_insert.side_effect = lambda readings, buffer_id=None: [
                {
                    "id": 100,
                    "device_id": readings[0].device_id,
                    "sensor_id": readings[0].sensor_id,
                    "timestamp": readings[0].timestamp,
                    "value": readings[0].value,
                    "unit": readings[0].unit,
                    "sequence": readings[0].sequence,
                    "received_at": datetime.now(timezone.utc),
                    "buffer_id": buffer_id,
                }
            ]
            
            ack = mqtt_client.ingest_batch(batch)
            
            # Validar que se guardó
            assert ack.accepted == 1
            
            # Validar que se evaluó umbral (alerta generada)
            mock_insert_alert.assert_called_once()
            alert_call = mock_insert_alert.call_args.kwargs
            assert alert_call["sensor_id"] == "TEMP-01"
            assert alert_call["threshold_excedido"] == "max"
            assert alert_call["severidad"] == "critico"  # 99 > 35 en >20%
    
    
    def test_e2e_http_endpoint_complete_flow(self):
        """
        Valida endpoint HTTP POST /readings/batch:
        1. Acepta buffer JSON
        2. Requiere autenticación
        3. Retorna ACK con db_id
        4. Publica ACK por MQTT
        """
        buffer_data = _buffer(device_id="ESP32-01", readings_count=2)
        
        from backend.auth import create_access_token
        token = create_access_token(data={"sub": "admin", "rol": "administrador"})
        
        with (
            patch("backend.db.get_buffer_readings", return_value=[]),
            patch("backend.db.insert_reading_batch") as mock_insert,
            patch("backend.db.get_threshold", return_value=None),
            patch("backend.db.insert_ingest_ack") as mock_insert_ack,
            patch("backend.mqtt_client.publish_ack") as mock_publish_ack,
            patch("backend.auth.get_user_by_username") as mock_get_user,
        ):
            # Mock user lookup
            mock_get_user.return_value = {
                "id": 1,
                "username": "admin",
                "password_hash": "$2b$12$...",
                "rol": "administrador"
            }
            
            # Mock insert_reading_batch
            mock_insert.side_effect = lambda readings, buffer_id=None: [
                {
                    "id": 100 + idx,
                    "device_id": r.device_id,
                    "sensor_id": r.sensor_id,
                    "timestamp": r.timestamp,
                    "value": r.value,
                    "unit": r.unit,
                    "sequence": r.sequence,
                    "received_at": datetime.now(timezone.utc),
                    "buffer_id": buffer_id,
                }
                for idx, r in enumerate(readings)
            ]
            
            # POST /readings/batch
            response = client.post(
                "/readings/batch",
                json=buffer_data,
                headers={"Authorization": f"Bearer {token}"},
            )
            
            # Validar respuesta
            assert response.status_code == 200
            data = response.json()
            assert data["type"] == "ack"
            assert data["buffer_id"] == buffer_data["buffer_id"]
            assert data["accepted"] == 2
            assert len(data["items"]) == 2
            assert all(item["db_id"] is not None for item in data["items"])
            
            # Validar que se registró en auditoría
            mock_insert_ack.assert_called_once()
            
            # Validar que se publicó por MQTT
            mock_publish_ack.assert_called_once()


class TestE2EAudit:
    """Tests de endpoints de auditoría."""
    
    def test_admin_can_query_ack_audit(self):
        """Admin puede consultar /admin/audit/acks."""
        from backend.auth import create_access_token
        token = create_access_token(data={"sub": "admin", "rol": "administrador"})
        
        with patch("backend.db.get_ingest_acks", return_value=[
            {
                "id": 1,
                "device_id": "ESP32-01",
                "buffer_id": "buf-001",
                "received_at": datetime.now(timezone.utc),
                "total_items": 2,
                "accepted": 2,
                "rejected": 0,
                "duplicates": 0,
            }
        ]):
            response = client.get(
                "/admin/audit/acks?limit=100",
                headers={"Authorization": f"Bearer {token}"},
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "acks" in data
        assert len(data["acks"]) == 1
    
    
    def test_observer_cannot_query_audit(self):
        """Observador NO puede consultar auditoría (403 Forbidden)."""
        from backend.auth import create_access_token
        token = create_access_token(data={"sub": "obs", "rol": "observador"})
        
        with patch("backend.auth.get_user_by_username") as mock_get_user:
            mock_get_user.return_value = {
                "id": 2,
                "username": "obs",
                "password_hash": "$2b$12$...",
                "rol": "observador"
            }
            response = client.get(
                "/admin/audit/acks",
                headers={"Authorization": f"Bearer {token}"},
            )
        
        assert response.status_code == 403
