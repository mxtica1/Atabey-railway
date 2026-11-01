import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import asyncio

from backend.main import app
from backend.ws_manager import manager
import backend.mqtt_client as mqtt_client

client = TestClient(app)

def mock_get_user_from_token(token: str):
    if token == "valid_token":
        from backend.models import User
        return User(id=1, username="admin", rol="administrador")
    return None

@patch("backend.main.get_user_from_token", side_effect=mock_get_user_from_token)
def test_ws_connection_success(mock_get_user):
    with client.websocket_connect("/ws/readings?token=valid_token") as websocket:
        assert len(manager.active_connections) == 1
        manager.disconnect(websocket)
        
@patch("backend.main.get_user_from_token", side_effect=mock_get_user_from_token)
def test_ws_connection_reject_invalid_token(mock_get_user):
    from fastapi.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/readings?token=invalid_token") as websocket:
            pass
    assert exc.value.code == 1008

def test_ws_connection_reject_no_token():
    from fastapi.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/readings") as websocket:
            pass

@patch("backend.main.get_user_from_token", side_effect=mock_get_user_from_token)
@patch("backend.db.insert_reading")
@patch("backend.db.get_threshold", return_value=None)
def test_ws_receives_message_on_mqtt_publish(mock_get_threshold, mock_insert_reading, mock_get_user):
    with client.websocket_connect("/ws/readings?token=valid_token") as websocket:
        def fake_broadcast_sync(msg):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.run_until_complete(manager.broadcast(msg))
            
        with patch.object(manager, "broadcast_sync", side_effect=fake_broadcast_sync):
            class MockMsg:
                payload = json.dumps({
                    "device_id": "ESP32-01",
                    "sensor_id": "TEMP-01",
                    "timestamp": "2026-09-24T20:15:00Z",
                    "value": 28.4,
                    "unit": "C",
                    "sequence": 1542
                }).encode("utf-8")
            
            mqtt_client.on_message(None, None, MockMsg())
            
            data = websocket.receive_json()
            assert data["sensor_id"] == "TEMP-01"
            assert data["value"] == 28.4
            assert data["unit"] == "C"
            assert data.get("type") == "reading"
            
        manager.disconnect(websocket)
