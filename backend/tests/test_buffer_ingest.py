"""
Tests del modulo 14 — buffer de datos, ACK, catalogo de sensores e ingesta.

Cubren (sin Docker, todo mockeado):
1.  ReadingBatch valida la estructura del buffer.
2.  ReadingBatch rechaza un buffer sin readings.
3.  ingest_batch guarda el buffer y devuelve un ACK item por lectura.
4.  ingest_batch es idempotente: el mismo buffer_id no se guarda dos veces.
5.  ingest_batch evalua umbrales con el mismo criterio que una lectura suelta.
6.  _handle_buffer publica el ACK en atabey/ack/{device_id}.
7.  on_message ramifica /buffer hacia _handle_buffer.
8.  on_message ignora los ACK publicados por el propio backend (sin eco).
9.  POST /readings/batch devuelve el ACK con el conteo correcto.
10. POST /readings/batch guarda con el buffer_id recibido.
11. POST /readings/batch requiere autenticacion (401 sin token).
12. GET /sensors/catalog devuelve el catalogo + los contratos.
13. El catalogo cubre TODOS los sensores definidos en el gateway.
14. El catalogo marca como biometricos solo HR/SPO2/BTEMP.
15. GET /ingest/recent devuelve received_at y sensor_id de cada registro.
16. GET /auth/mode informa si hace falta login.
17. Con REQUIRE_LOGIN=false el backend acepta peticiones sin token.
18. Con REQUIRE_LOGIN=true el backend sigue exigiendo token.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import backend.mqtt_client as mqtt_client
from backend.main import app
from backend.models import ReadingBatch

client = TestClient(app)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _mk_token(rol: str) -> str:
    from backend.auth import create_access_token
    return create_access_token(data={"sub": rol, "rol": rol})


def _mock_db_user(rol: str) -> dict:
    from passlib.context import CryptContext
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return {"id": 1, "username": rol, "password_hash": ctx.hash("pass"), "rol": rol}


def _reading(sensor_id="TEMP-01", value=28.4, sequence=1, device_id="ESP32-01"):
    return {
        "device_id": device_id,
        "sensor_id": sensor_id,
        "timestamp": "2026-10-31T18:00:00Z",
        "value": value,
        "unit": "C",
        "sequence": sequence,
    }


VALID_BUFFER = {
    "device_id": "ESP32-01",
    "buffer_id": "buf-0001",
    "sent_at": "2026-10-31T18:00:05Z",
    "readings": [
        _reading("TEMP-01", 28.4, 1),
        _reading("HUM-01", 62.0, 7, ),
    ],
}


def _mqtt_msg(topic: str, payload: dict):
    msg = MagicMock()
    msg.topic = topic
    msg.payload = json.dumps(payload).encode("utf-8")
    return msg


def _fake_rows(batch_readings, buffer_id):
    """Simula lo que devuelve db.insert_reading_batch."""
    now = datetime.now(timezone.utc)
    return [
        {
            "id": 100 + index,
            "device_id": r.device_id,
            "sensor_id": r.sensor_id,
            "timestamp": r.timestamp,
            "value": r.value,
            "unit": r.unit,
            "sequence": r.sequence,
            "received_at": now,
            "buffer_id": buffer_id,
        }
        for index, r in enumerate(batch_readings)
    ]


# ── 1-2. Modelo ReadingBatch ─────────────────────────────────────────────────

def test_reading_batch_valida_estructura():
    batch = ReadingBatch(**VALID_BUFFER)
    assert batch.device_id == "ESP32-01"
    assert batch.buffer_id == "buf-0001"
    assert len(batch.readings) == 2
    assert batch.readings[0].sensor_id == "TEMP-01"


def test_reading_batch_rechaza_sin_readings():
    from pydantic import Field
    with pytest.raises(ValidationError):
        ReadingBatch(device_id="ESP32-01", buffer_id="b1", readings=[])


def test_reading_batch_rechaza_lectura_invalida():
    bad = {**VALID_BUFFER, "readings": [{"sensor_id": "TEMP-01"}]}
    with pytest.raises(ValidationError):
        ReadingBatch(**bad)


# ── 3. ingest_batch guarda y devuelve ACK ────────────────────────────────────

def test_ingest_batch_devuelve_ack_por_lectura():
    batch = ReadingBatch(**VALID_BUFFER)
    with (
        patch("backend.db.get_buffer_readings", return_value=[]),
        patch("backend.db.insert_reading_batch") as mock_insert,
        patch("backend.db.get_threshold", return_value=None),
        patch("backend.db.insert_ingest_ack") as mock_insert_ack,
    ):
        mock_insert.side_effect = lambda readings, buffer_id=None: _fake_rows(readings, buffer_id)
        ack = mqtt_client.ingest_batch(batch)

    assert ack.type == "ack"
    assert ack.device_id == "ESP32-01"
    assert ack.buffer_id == "buf-0001"
    assert ack.accepted == 2
    assert ack.rejected == 0
    assert ack.duplicates == 0
    assert len(ack.items) == 2
    assert ack.items[0].sensor_id == "TEMP-01"
    assert ack.items[0].status == "stored"
    assert ack.items[0].db_id == 100
    assert ack.items[0].received_at is not None
    assert ack.items[1].sensor_id == "HUM-01"
    assert ack.received_at is not None


# ── 4. Idempotencia ──────────────────────────────────────────────────────────

def test_ingest_batch_es_idempotente():
    """El mismo buffer_id reenviado no se guarda dos veces."""
    batch = ReadingBatch(**VALID_BUFFER)
    ya_guardadas = [
        {
            "id": 7, "device_id": "ESP32-01", "sensor_id": "TEMP-01",
            "timestamp": datetime.now(timezone.utc), "value": 28.4, "unit": "C",
            "sequence": 1, "received_at": datetime.now(timezone.utc),
            "buffer_id": "buf-0001",
        }
    ]
    with (
        patch("backend.db.get_buffer_readings", return_value=ya_guardadas),
        patch("backend.db.insert_reading_batch") as mock_insert,
        patch("backend.db.insert_ingest_ack") as mock_insert_ack,
    ):
        ack = mqtt_client.ingest_batch(batch)

    mock_insert.assert_not_called()
    assert ack.accepted == 0
    assert ack.duplicates == 1
    assert ack.items[0].status == "duplicate"
    assert ack.items[0].db_id == 7


# ── 5. Umbrales en el buffer ─────────────────────────────────────────────────

def test_ingest_batch_evalua_umbrales():
    """Una lectura fuera de umbral genera alerta (mismo criterio que lectura suelta)."""
    batch = ReadingBatch(**{
        **VALID_BUFFER,
        "readings": [_reading("TEMP-01", 99.0, 1)],
    })
    threshold = {"sensor_id": "TEMP-01", "valor_min": 15.0, "valor_max": 35.0}
    with (
        patch("backend.db.get_buffer_readings", return_value=[]),
        patch("backend.db.insert_reading_batch") as mock_insert,
        patch("backend.db.get_threshold", return_value=threshold),
        patch("backend.db.get_active_alert", return_value=None),
        patch("backend.db.insert_alert") as mock_alert,
        patch("backend.db.insert_ingest_ack") as mock_insert_ack,
    ):
        mock_insert.side_effect = lambda readings, buffer_id=None: _fake_rows(readings, buffer_id)
        mock_alert.return_value = {"id": 55, "severidad": "critico"}
        mqtt_client.ingest_batch(batch)

    mock_alert.assert_called_once()
    kwargs = mock_alert.call_args.kwargs
    assert kwargs["sensor_id"] == "TEMP-01"
    assert kwargs["threshold_excedido"] == "max"
    assert kwargs["severidad"] == "critico"   # margen 64 > 20% del rango (20)


def test_ingest_batch_no_alerta_si_dentro_de_rango():
    batch = ReadingBatch(**{
        **VALID_BUFFER,
        "readings": [_reading("TEMP-01", 25.0, 1)],
    })
    threshold = {"sensor_id": "TEMP-01", "valor_min": 15.0, "valor_max": 35.0}
    with (
        patch("backend.db.get_buffer_readings", return_value=[]),
        patch("backend.db.insert_reading_batch") as mock_insert,
        patch("backend.db.get_threshold", return_value=threshold),
        patch("backend.db.get_active_alert", return_value=None),
        patch("backend.db.insert_alert") as mock_alert,
        patch("backend.db.insert_ingest_ack") as mock_insert_ack,
    ):
        mock_insert.side_effect = lambda readings, buffer_id=None: _fake_rows(readings, buffer_id)
        mqtt_client.ingest_batch(batch)

    mock_alert.assert_not_called()


# ── 6. _handle_buffer publica el ACK ────────────────────────────────────────

def test_handle_buffer_publica_ack():
    with (
        patch("backend.db.get_buffer_readings", return_value=[]),
        patch("backend.db.insert_reading_batch") as mock_insert,
        patch("backend.db.get_threshold", return_value=None),
        patch("backend.db.insert_ingest_ack") as mock_insert_ack,
        patch("backend.mqtt_client.publish_ack") as mock_publish,
    ):
        mock_insert.side_effect = lambda readings, buffer_id=None: _fake_rows(readings, buffer_id)
        mqtt_client._handle_buffer(_mqtt_msg("atabey/ESP32-01/buffer", VALID_BUFFER))

    mock_publish.assert_called_once()
    ack = mock_publish.call_args[0][0]
    assert ack.buffer_id == "buf-0001"
    assert ack.accepted == 2


def test_publish_ack_usa_el_topico_correcto():
    """El ACK se publica en atabey/ack/{device_id}."""
    fake_client = MagicMock()
    fake_client.publish.return_value = MagicMock(rc=0)
    with patch("backend.mqtt_client._client", fake_client):
        from backend.models import BatchAck, BatchItemAck
        a = BatchAck(
            device_id="ESP32-01",
            buffer_id="buf-9",
            received_at=datetime.now(timezone.utc),
            accepted=1, rejected=0, duplicates=0,
            items=[BatchItemAck(sensor_id="TEMP-01", sequence=1, status="stored")],
        )
        mqtt_client.publish_ack(a)

    fake_client.publish.assert_called_once()
    args, _ = fake_client.publish.call_args
    assert args[0] == "atabey/ack/ESP32-01"
    payload = json.loads(args[1])
    assert payload["type"] == "ack"
    assert payload["buffer_id"] == "buf-9"
    assert payload["accepted"] == 1


# ── 7-8. Ramificacion por topico ────────────────────────────────────────────

def test_topico_buffer_llama_handle_buffer():
    with patch("backend.mqtt_client._handle_buffer") as mock_buf, \
         patch("backend.mqtt_client._handle_reading") as mock_read:
        mqtt_client.on_message(None, None, _mqtt_msg("atabey/ESP32-01/buffer", VALID_BUFFER))
    mock_buf.assert_called_once()
    mock_read.assert_not_called()


def test_ack_publicado_no_genera_eco():
    """Los ACK que publica el backend no se reingieren."""
    with patch("backend.mqtt_client._handle_buffer") as mock_buf, \
         patch("backend.mqtt_client._handle_reading") as mock_read:
        mqtt_client.on_message(None, None, _mqtt_msg("atabey/ack/ESP32-01", {"type": "ack"}))
    mock_buf.assert_not_called()
    mock_read.assert_not_called()


# ── 9-11. POST /readings/batch ───────────────────────────────────────────────

def test_post_readings_batch_devuelve_ack():
    with (
        patch("backend.db.get_buffer_readings", return_value=[]),
        patch("backend.db.insert_reading_batch") as mock_insert,
        patch("backend.db.get_threshold", return_value=None),
        patch("backend.db.insert_ingest_ack") as mock_insert_ack,
        patch("backend.mqtt_client.publish_ack"),
        patch("backend.auth.get_user_by_username", return_value=_mock_db_user("administrador")),
    ):
        mock_insert.side_effect = lambda readings, buffer_id=None: _fake_rows(readings, buffer_id)
        response = client.post(
            "/readings/batch",
            json=VALID_BUFFER,
            headers={"Authorization": f"Bearer {_mk_token('administrador')}"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "ack"
    assert data["buffer_id"] == "buf-0001"
    assert data["accepted"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["sensor_id"] == "TEMP-01"
    assert data["items"][0]["status"] == "stored"
    assert data["items"][0]["received_at"] is not None
    assert data["items"][0]["db_id"] == 100


def test_post_readings_batch_guarda_con_buffer_id():
    with (
        patch("backend.db.get_buffer_readings", return_value=[]),
        patch("backend.db.insert_reading_batch") as mock_insert,
        patch("backend.db.get_threshold", return_value=None),
        patch("backend.db.insert_ingest_ack") as mock_insert_ack,
        patch("backend.mqtt_client.publish_ack"),
        patch("backend.auth.get_user_by_username", return_value=_mock_db_user("administrador")),
    ):
        mock_insert.side_effect = lambda readings, buffer_id=None: _fake_rows(readings, buffer_id)
        client.post(
            "/readings/batch",
            json=VALID_BUFFER,
            headers={"Authorization": f"Bearer {_mk_token('administrador')}"},
        )
    assert mock_insert.call_args.kwargs["buffer_id"] == "buf-0001"


def test_post_readings_batch_sin_token_401():
    with (
        patch("backend.db.get_buffer_readings", return_value=[]),
        patch("backend.db.insert_reading_batch"),
        patch("backend.db.get_threshold", return_value=None),
        patch("backend.mqtt_client.publish_ack"),
    ):
        response = client.post("/readings/batch", json=VALID_BUFFER)
    assert response.status_code == 401


# ── 12-14. GET /sensors/catalog ──────────────────────────────────────────────

def test_get_sensors_catalog():
    with patch("backend.auth.get_user_by_username", return_value=_mock_db_user("administrador")):
        response = client.get(
            "/sensors/catalog",
            headers={"Authorization": f"Bearer {_mk_token('administrador')}"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["total_sensors"] == len(data["devices"][0]["sensors"]) + len(data["devices"][1]["sensors"])
    # Contratos presentes
    contract = data["contract"]
    assert "reading" in contract
    assert "buffer" in contract
    assert "ack" in contract
    assert contract["mqtt"]["buffer_topic"] == "atabey/{device_id}/buffer"
    assert contract["mqtt"]["ack_topic"] == "atabey/ack/{device_id}"


def test_catalogo_cubre_todos_los_sensores_del_gateway():
    """El catalogo debe incluir cada sensor_id que el gateway genera."""
    from gateway.domo_sensors import make_domo_sensors
    from gateway.tripulante_sensors import make_tripulante_sensors

    import backend.catalog as catalog

    gateway_ids = {s.sensor_id for s in make_domo_sensors()}
    gateway_ids |= {s.sensor_id for s in make_tripulante_sensors()}
    catalog_ids = set(catalog.BY_SENSOR_ID.keys())

    faltantes = gateway_ids - catalog_ids
    assert not faltantes, f"Sensores del gateway sin catalogar: {sorted(faltantes)}"


def test_catalogo_marca_biometricos():
    import backend.catalog as catalog
    assert catalog.BIOMETRIC_SENSOR_IDS == frozenset({"HR-01", "SPO2-01", "BTEMP-01"})
    for entry in catalog.CATALOG:
        if entry["sensor_id"] in ("HR-01", "SPO2-01", "BTEMP-01"):
            assert entry["biometrico"] is True
        else:
            assert entry["biometrico"] is False


def test_catalogo_tiene_variable_para_cada_sensor():
    """Cada sensor expone un nombre de variable usable en el buffer."""
    import backend.catalog as catalog
    for entry in catalog.CATALOG:
        assert entry["variable"], f"{entry['sensor_id']} sin variable"
        assert entry["unit"] != "" or entry["sensor_id"] == "ACTIVITY-01"
        assert entry["device_id"] in ("ESP32-01", "EVA-01")


# ── 15. GET /ingest/recent ───────────────────────────────────────────────────

def test_get_ingest_recent():
    now = datetime.now(timezone.utc)
    rows = [
        {
            "id": 1, "device_id": "ESP32-01", "sensor_id": "TEMP-01",
            "value": 28.4, "unit": "C", "timestamp": now,
            "received_at": now, "buffer_id": "buf-0001", "sequence": 1,
        },
        {
            "id": 2, "device_id": "ESP32-01", "sensor_id": "HUM-01",
            "value": 62.0, "unit": "%", "timestamp": now,
            "received_at": now, "buffer_id": "buf-0001", "sequence": 7,
        },
    ]
    with (
        patch("backend.db.get_recent_ingest", return_value=rows),
        patch("backend.auth.get_user_by_username", return_value=_mock_db_user("administrador")),
    ):
        response = client.get(
            "/ingest/recent",
            headers={"Authorization": f"Bearer {_mk_token('administrador')}"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["records"]) == 2
    # Cada registro dice de que sensor vino y cuando se guardo
    assert data["records"][0]["sensor_id"] == "TEMP-01"
    assert data["records"][0]["received_at"] is not None
    assert data["records"][0]["buffer_id"] == "buf-0001"
    # Agrupacion por buffer
    assert len(data["buffers"]) == 1
    assert data["buffers"][0]["buffer_id"] == "buf-0001"
    assert data["buffers"][0]["readings"] == 2
    assert set(data["buffers"][0]["sensors"]) == {"TEMP-01", "HUM-01"}


# ── 16-18. Modo de autenticacion ─────────────────────────────────────────────

def test_get_auth_mode():
    response = client.get("/auth/mode")
    assert response.status_code == 200
    data = response.json()
    assert "requires_login" in data
    assert data["default_rol"] in ("administrador", "control_mision", "observador")


def test_auth_anonimo_acepta_sin_token():
    """Con REQUIRE_LOGIN=false, los endpoints aceptan peticiones sin token."""
    with (
        patch("backend.auth.REQUIRE_LOGIN", False),
        patch("backend.auth.DEFAULT_ROL", "administrador"),
        patch("backend.db.get_buffer_readings", return_value=[]),
        patch("backend.db.insert_reading_batch") as mock_insert,
        patch("backend.db.get_threshold", return_value=None),
        patch("backend.db.insert_ingest_ack") as mock_insert_ack,
        patch("backend.mqtt_client.publish_ack"),
    ):
        mock_insert.side_effect = lambda readings, buffer_id=None: _fake_rows(readings, buffer_id)
        response = client.post("/readings/batch", json=VALID_BUFFER)
    assert response.status_code == 200
    assert response.json()["accepted"] == 2


def test_auth_requerido_sigue_exigiendo_token():
    with patch("backend.auth.REQUIRE_LOGIN", True):
        response = client.post("/readings/batch", json=VALID_BUFFER)
    assert response.status_code == 401
