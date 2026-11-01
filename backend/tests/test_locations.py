"""
Tests del modulo 12 — coordenadas del tripulante (backend).

Cubren (sin Docker, todo mockeado):
1.  Modelo LocationUpdate valida campos correctos.
2.  LocationUpdate rechaza payload con campos ausentes.
3.  LocationUpdate rechaza tipos incorrectos.
4.  Mensaje en topico /location es procesado por _handle_location, no _handle_reading.
5.  Mensaje en topico sin /location es procesado por _handle_reading, no _handle_location.
6.  _handle_location inserta en DB y hace broadcast type='location'.
7.  _handle_location descarta JSON invalido sin tumbar el backend.
8.  _handle_location descarta payload con esquema incorrecto sin tumbar el backend.
9.  GET /locations/latest devuelve la posicion mas reciente.
10. GET /locations/latest devuelve 404 si no hay posiciones.
11. GET /locations/latest requiere autenticacion (401 sin token).
12. Todos los roles (admin, control_mision, observador) pueden ver /locations/latest.
13. El WS entrega mensajes type='location' a todos los roles sin filtrar.
14. LocationUpdate acepta `sexo` opcional ("M" / "F").
15. LocationUpdate acepta payload sin `sexo` (compatibilidad hacia atras).
16. _handle_location propaga `sexo` al broadcast WS.
17. GET /tripulantes devuelve metadata (device_id, sexo) para todos los roles.
"""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import backend.mqtt_client as mqtt_client
from backend.main import app
from backend.models import LocationUpdate
from backend.ws_manager import manager

client = TestClient(app)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _token_for(rol: str) -> str:
    from backend.auth import create_access_token
    return create_access_token(data={"sub": rol, "rol": rol})


def _mock_db_user(rol: str) -> dict:
    from passlib.context import CryptContext
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return {"id": 1, "username": rol, "password_hash": ctx.hash("pass"), "rol": rol}


VALID_LOC_PAYLOAD = {
    "device_id": "EVA-01",
    "timestamp": "2026-09-24T20:15:00Z",
    "lat": 18.8776,
    "lon": -70.5609,
    "sequence": 1,
}

VALID_LOC_DB = {
    "id": 1,
    "device_id": "EVA-01",
    "timestamp": datetime(2026, 9, 24, 20, 15, 0, tzinfo=timezone.utc),
    "lat": 18.8776,
    "lon": -70.5609,
    "sequence": 1,
    "sexo": "F",
}


def _make_mqtt_msg(topic: str, payload: dict) -> object:
    class _Msg:
        pass
    m = _Msg()
    m.topic   = topic
    m.payload = json.dumps(payload).encode("utf-8")
    return m


# ── 1-3. Validacion del modelo LocationUpdate ─────────────────────────────────

def test_location_update_valida_campos_correctos():
    loc = LocationUpdate(**VALID_LOC_PAYLOAD)
    assert loc.device_id == "EVA-01"
    assert loc.lat == 18.8776
    assert loc.lon == -70.5609
    assert loc.sequence == 1
    assert isinstance(loc.timestamp, datetime)


def test_location_update_rechaza_campos_ausentes():
    from pydantic import ValidationError
    payload = {k: v for k, v in VALID_LOC_PAYLOAD.items() if k != "lat"}
    with pytest.raises(ValidationError):
        LocationUpdate(**payload)


def test_location_update_rechaza_tipos_incorrectos():
    from pydantic import ValidationError
    payload = {**VALID_LOC_PAYLOAD, "lat": "no-es-float"}
    with pytest.raises(ValidationError):
        LocationUpdate(**payload)


def test_location_update_acepta_sexo_opcional():
    """`sexo` es opcional y acepta solo 'M' o 'F'."""
    payload_m = {**VALID_LOC_PAYLOAD, "sexo": "M"}
    payload_f = {**VALID_LOC_PAYLOAD, "sexo": "F"}
    payload_none = {**VALID_LOC_PAYLOAD, "sexo": None}

    loc_m = LocationUpdate(**payload_m)
    loc_f = LocationUpdate(**payload_f)
    loc_none = LocationUpdate(**payload_none)

    assert loc_m.sexo == "M"
    assert loc_f.sexo == "F"
    assert loc_none.sexo is None


def test_location_update_acepta_payload_sin_sexo():
    """Compatibilidad hacia atras: payload sin `sexo` sigue siendo valido."""
    assert "sexo" not in VALID_LOC_PAYLOAD
    loc = LocationUpdate(**VALID_LOC_PAYLOAD)
    assert loc.sexo is None


def test_location_update_rechaza_sexo_invalido():
    """Cualquier valor fuera de {'M','F'} debe ser rechazado."""
    from pydantic import ValidationError
    payload = {**VALID_LOC_PAYLOAD, "sexo": "X"}
    with pytest.raises(ValidationError):
        LocationUpdate(**payload)


def test_handle_location_propaga_sexo_en_broadcast():
    """El broadcast WS incluye `sexo` cuando viene en el payload."""
    payload_with_sexo = {**VALID_LOC_PAYLOAD, "sexo": "M"}
    msg = _make_mqtt_msg("atabey/eva/EVA-01/location", payload_with_sexo)
    with patch("backend.mqtt_client.db.insert_location", return_value={**VALID_LOC_DB, "sexo": "M"}), \
         patch("backend.mqtt_client.manager.broadcast_sync") as mock_bs:
        mqtt_client._handle_location(msg)

    mock_bs.assert_called_once()
    broadcast_msg = mock_bs.call_args[0][0]
    assert broadcast_msg["sexo"] == "M"


def test_handle_location_omite_sexo_si_no_viene():
    """Cuando `sexo` no viene, el broadcast incluye None (no rompe el contrato)."""
    msg = _make_mqtt_msg("atabey/eva/EVA-01/location", VALID_LOC_PAYLOAD)
    with patch("backend.mqtt_client.db.insert_location", return_value=VALID_LOC_DB), \
         patch("backend.mqtt_client.manager.broadcast_sync") as mock_bs:
        mqtt_client._handle_location(msg)

    broadcast_msg = mock_bs.call_args[0][0]
    assert broadcast_msg["sexo"] is None


# ── 4-5. Ramificacion por topico en on_message ────────────────────────────────

@patch("backend.mqtt_client._handle_location")
@patch("backend.mqtt_client._handle_reading")
def test_topico_location_llama_handle_location(mock_reading, mock_location):
    msg = _make_mqtt_msg("atabey/eva/EVA-01/location", VALID_LOC_PAYLOAD)
    mqtt_client.on_message(None, None, msg)
    mock_location.assert_called_once()
    mock_reading.assert_not_called()


@patch("backend.mqtt_client._handle_location")
@patch("backend.mqtt_client._handle_reading")
def test_topico_sensor_llama_handle_reading(mock_reading, mock_location):
    msg = _make_mqtt_msg("atabey/domo/TEMP-01", {
        "device_id": "ESP32-01", "sensor_id": "TEMP-01",
        "timestamp": "2026-09-24T20:15:00Z", "value": 25.0, "unit": "C", "sequence": 1,
    })
    mqtt_client.on_message(None, None, msg)
    mock_reading.assert_called_once()
    mock_location.assert_not_called()


# ── 6. _handle_location inserta en DB y hace broadcast ───────────────────────

@patch("backend.mqtt_client.db.insert_location", return_value=VALID_LOC_DB)
@patch("backend.mqtt_client.manager.broadcast_sync")
def test_handle_location_inserta_y_hace_broadcast(mock_bs, mock_insert):
    msg = _make_mqtt_msg("atabey/eva/EVA-01/location", VALID_LOC_PAYLOAD)
    mqtt_client._handle_location(msg)

    mock_insert.assert_called_once()
    loc_arg = mock_insert.call_args[0][0]
    assert isinstance(loc_arg, LocationUpdate)
    assert loc_arg.device_id == "EVA-01"
    assert loc_arg.lat == 18.8776

    mock_bs.assert_called_once()
    broadcast_msg = mock_bs.call_args[0][0]
    assert broadcast_msg["type"] == "location"
    assert broadcast_msg["device_id"] == "EVA-01"
    assert broadcast_msg["lat"] == 18.8776
    assert broadcast_msg["lon"] == -70.5609


# ── 7-8. _handle_location descarta mensajes invalidos ─────────────────────────

@patch("backend.mqtt_client.db.insert_location")
@patch("backend.mqtt_client.manager.broadcast_sync")
def test_handle_location_json_invalido_no_tumba(mock_bs, mock_insert):
    class _BadMsg:
        topic   = "atabey/eva/EVA-01/location"
        payload = b"esto no es json {"
    mqtt_client._handle_location(_BadMsg())
    mock_insert.assert_not_called()


@patch("backend.mqtt_client.db.insert_location")
@patch("backend.mqtt_client.manager.broadcast_sync")
def test_handle_location_esquema_incorrecto_no_tumba(mock_bs, mock_insert):
    bad = {"device_id": "EVA-01", "lat": "no-es-float"}
    msg = _make_mqtt_msg("atabey/eva/EVA-01/location", bad)
    mqtt_client._handle_location(msg)
    mock_insert.assert_not_called()


# ── 9. GET /locations/latest devuelve la posicion ─────────────────────────────

@patch("backend.auth.get_user_by_username")
@patch("backend.db.get_latest_location", return_value=VALID_LOC_DB)
def test_get_latest_location_devuelve_datos(mock_get_loc, mock_get_user):
    mock_get_user.return_value = _mock_db_user("administrador")
    token = _token_for("administrador")
    response = client.get(
        "/locations/latest?device_id=EVA-01",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["device_id"] == "EVA-01"
    assert data["lat"] == 18.8776
    assert data["lon"] == -70.5609


# ── 10. GET /locations/latest devuelve 404 si no hay posiciones ───────────────

@patch("backend.auth.get_user_by_username")
@patch("backend.db.get_latest_location", return_value=None)
def test_get_latest_location_404(mock_get_loc, mock_get_user):
    mock_get_user.return_value = _mock_db_user("administrador")
    token = _token_for("administrador")
    response = client.get(
        "/locations/latest?device_id=EVA-99",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


# ── 11. GET /locations/latest requiere autenticacion ─────────────────────────

def test_get_latest_location_sin_token_401():
    response = client.get("/locations/latest?device_id=EVA-01")
    assert response.status_code == 401


# ── 12. Todos los roles pueden ver /locations/latest ──────────────────────────

@pytest.mark.parametrize("rol", ["administrador", "control_mision", "observador"])
@patch("backend.db.get_latest_location", return_value=VALID_LOC_DB)
def test_todos_los_roles_ven_location(mock_get_loc, rol):
    with patch("backend.auth.get_user_by_username", return_value=_mock_db_user(rol)):
        token = _token_for(rol)
        response = client.get(
            "/locations/latest?device_id=EVA-01",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200


# ── 13. WS entrega location a todos los roles ─────────────────────────────────

def _make_ws_mock_conn():
    ws = MagicMock()
    ws.send_text = AsyncMock()
    return ws


def _run_broadcast(msg: dict) -> None:
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(manager.broadcast(msg))
    finally:
        loop.close()


@pytest.mark.parametrize("rol", ["administrador", "control_mision", "observador"])
def test_ws_entrega_location_a_todos_los_roles(rol):
    ws = _make_ws_mock_conn()
    manager.connections[ws] = rol
    try:
        _run_broadcast({
            "type": "location",
            "device_id": "EVA-01",
            "lat": 18.8776,
            "lon": -70.5609,
            "timestamp": "2026-09-24T20:15:00Z",
            "sequence": 1,
        })
        ws.send_text.assert_called_once()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "location"
        assert sent["device_id"] == "EVA-01"
    finally:
        manager.connections.pop(ws, None)


# ── 17. GET /tripulantes devuelve metadata de la tripulacion ──────────────────

@pytest.mark.parametrize("rol", ["administrador", "control_mision", "observador"])
@patch("backend.db.get_tripulantes_meta")
def test_tripulantes_devuelve_metadata(mock_meta, rol):
    """GET /tripulantes accesible para todos los roles autenticados."""
    mock_meta.return_value = [
        {"device_id": "EVA-01", "sexo": "F"},
        {"device_id": "EVA-02", "sexo": "M"},
    ]
    with patch("backend.auth.get_user_by_username", return_value=_mock_db_user(rol)):
        token = _token_for(rol)
        response = client.get(
            "/tripulantes",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0] == {"device_id": "EVA-01", "sexo": "F"}
    assert data[1] == {"device_id": "EVA-02", "sexo": "M"}


def test_tripulantes_sin_token_401():
    """Sin token, /tripulantes responde 401."""
    response = client.get("/tripulantes")
    assert response.status_code == 401


@patch("backend.db.get_tripulantes_meta")
def test_tripulantes_puede_devolver_sexo_none(mock_meta):
    """Si no hay sexo registrado, devuelve None (no rompe la respuesta)."""
    mock_meta.return_value = [{"device_id": "EVA-99", "sexo": None}]
    with patch("backend.auth.get_user_by_username", return_value=_mock_db_user("administrador")):
        token = _token_for("administrador")
        response = client.get(
            "/tripulantes",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert response.json() == [{"device_id": "EVA-99", "sexo": None}]
