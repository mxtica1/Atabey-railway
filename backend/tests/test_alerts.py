"""
Tests del modulo de alertas por umbral configurable + ciclo de vida.

Cubren (sin Docker, todo mockeado):

1.  Lectura fuera de rango (por encima) genera alerta nueva cuando no hay activa.
2.  Lectura fuera de rango (por debajo) genera alerta nueva cuando no hay activa.
3.  Lectura dentro de rango NO genera alerta.
4.  Sensor sin umbral configurado NO genera alerta.
5.  Observador NO recibe alerta de sensor biometrico via manager.broadcast.
6.  Observador SI recibe alerta de sensor tecnico via manager.broadcast.
7.  Administrador y control_mision reciben alertas biometricas via manager.broadcast.
8.  GET /alerts/active filtra biometricos para observador (REST).
9.  GET /alerts/active devuelve alertas para administrador sin filtrar.
10. Administrador puede actualizar umbral via PUT /admin/thresholds/{sensor_id}.
11. Observador recibe 403 en PUT /admin/thresholds/{sensor_id}.
12. Una lectura posterior usa el nuevo umbral (integracion de upsert + check).
13. PUT con valor_min >= valor_max devuelve 422.
14. GET /admin/thresholds devuelve lista de umbrales.
15. Observador recibe 403 en GET /admin/thresholds.

Ciclo de vida (deduplicacion + resolucion):
16. Lecturas consecutivas fuera de rango actualizan la alerta existente, no crean nueva.
17. Lectura que vuelve a rango resuelve automaticamente la alerta activa.
18. Tras auto-resolucion, nueva lectura fuera de rango crea alerta NUEVA.
19. PATCH /alerts/{id}/resolve marca la alerta como resuelta manualmente.
20. Observador recibe 403 en PATCH /alerts/{id}/resolve.
21. PATCH sobre alerta ya resuelta devuelve 409.
22. PATCH sobre alerta inexistente devuelve 404.
"""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from fastapi.testclient import TestClient

import backend.mqtt_client as mqtt_client
from backend.main import app
from backend.ws_manager import BIOMETRIC_SENSORS, manager

client = TestClient(app)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _token_for(rol: str) -> str:
    from backend.auth import create_access_token
    return create_access_token(data={"sub": rol, "rol": rol})


def _mock_db_user(rol: str) -> dict:
    from passlib.context import CryptContext
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return {"id": 1, "username": rol, "password_hash": ctx.hash("pass"), "rol": rol}


def _make_mqtt_msg(sensor_id: str, value: float, unit: str = "C", seq: int = 1) -> object:
    class _Msg:
        payload = json.dumps({
            "device_id": "ESP32-01",
            "sensor_id": sensor_id,
            "timestamp": "2026-09-24T20:15:00Z",
            "value": value,
            "unit": unit,
            "sequence": seq,
        }).encode("utf-8")
    return _Msg()


def _make_ws_mock():
    ws = MagicMock()
    ws.send_text = AsyncMock()
    return ws


def _run_broadcast(msg: dict) -> None:
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(manager.broadcast(msg))
    finally:
        loop.close()


_THRESHOLD_TEMP = {"sensor_id": "TEMP-01", "valor_min": -10.0, "valor_max": 50.0}
_THRESHOLD_HR   = {"sensor_id": "HR-01",   "valor_min": 40.0,  "valor_max": 180.0}

_ALERT_TEMP = {
    "id": 1, "sensor_id": "TEMP-01", "value": 55.0,
    "threshold_excedido": "max", "valor_min": -10.0, "valor_max": 50.0,
    "timestamp": datetime(2026, 9, 24, 20, 15, 0, tzinfo=timezone.utc),
    "severidad": "advertencia", "resuelto": False,
    "visto_por_ultima_vez": None, "resuelto_en": None, "resuelto_por": None,
}
_ALERT_HR = {
    "id": 2, "sensor_id": "HR-01", "value": 200.0,
    "threshold_excedido": "max", "valor_min": 40.0, "valor_max": 180.0,
    "timestamp": datetime(2026, 9, 24, 20, 15, 0, tzinfo=timezone.utc),
    "severidad": "critico", "resuelto": False,
    "visto_por_ultima_vez": None, "resuelto_en": None, "resuelto_por": None,
}


# ── 1. Lectura fuera de rango por encima genera alerta nueva ─────────────────

@patch("backend.mqtt_client.db.insert_reading")
@patch("backend.mqtt_client.db.get_threshold", return_value=_THRESHOLD_TEMP)
@patch("backend.mqtt_client.db.get_active_alert", return_value=None)
@patch("backend.mqtt_client.db.insert_alert", return_value={**_ALERT_TEMP})
@patch("backend.mqtt_client.manager.broadcast_sync")
def test_lectura_fuera_de_rango_max_genera_alerta(mock_bs, mock_insert_alert, mock_get_active, mock_threshold, mock_insert):
    mqtt_client.on_message(None, None, _make_mqtt_msg("TEMP-01", value=55.0))

    mock_insert_alert.assert_called_once()
    args = mock_insert_alert.call_args
    assert args.kwargs["sensor_id"] == "TEMP-01"
    assert args.kwargs["threshold_excedido"] == "max"
    assert args.kwargs["value"] == 55.0

    # broadcast llamado dos veces: lectura + alerta
    assert mock_bs.call_count == 2
    alert_msg = mock_bs.call_args_list[1][0][0]
    assert alert_msg["type"] == "alert"
    assert alert_msg["sensor_id"] == "TEMP-01"
    assert alert_msg["threshold_excedido"] == "max"


# ── 2. Lectura fuera de rango por debajo genera alerta nueva ─────────────────

@patch("backend.mqtt_client.db.insert_reading")
@patch("backend.mqtt_client.db.get_threshold", return_value=_THRESHOLD_TEMP)
@patch("backend.mqtt_client.db.get_active_alert", return_value=None)
@patch("backend.mqtt_client.db.insert_alert", return_value={**_ALERT_TEMP, "threshold_excedido": "min", "value": -20.0})
@patch("backend.mqtt_client.manager.broadcast_sync")
def test_lectura_fuera_de_rango_min_genera_alerta(mock_bs, mock_insert_alert, mock_get_active, mock_threshold, mock_insert):
    mqtt_client.on_message(None, None, _make_mqtt_msg("TEMP-01", value=-20.0))

    mock_insert_alert.assert_called_once()
    assert mock_insert_alert.call_args.kwargs["threshold_excedido"] == "min"

    alert_msg = mock_bs.call_args_list[1][0][0]
    assert alert_msg["type"] == "alert"
    assert alert_msg["threshold_excedido"] == "min"


# ── 3. Lectura dentro de rango NO genera alerta ───────────────────────────────

@patch("backend.mqtt_client.db.insert_reading")
@patch("backend.mqtt_client.db.get_threshold", return_value=_THRESHOLD_TEMP)
@patch("backend.mqtt_client.db.get_active_alert", return_value=None)
@patch("backend.mqtt_client.db.insert_alert")
@patch("backend.mqtt_client.manager.broadcast_sync")
def test_lectura_dentro_de_rango_no_genera_alerta(mock_bs, mock_insert_alert, mock_get_active, mock_threshold, mock_insert):
    mqtt_client.on_message(None, None, _make_mqtt_msg("TEMP-01", value=25.0))

    mock_insert_alert.assert_not_called()
    # Solo un broadcast (la lectura normal)
    assert mock_bs.call_count == 1
    assert mock_bs.call_args[0][0]["type"] == "reading"


# ── 4. Sensor sin umbral NO genera alerta ────────────────────────────────────

@patch("backend.mqtt_client.db.insert_reading")
@patch("backend.mqtt_client.db.get_threshold", return_value=None)
@patch("backend.mqtt_client.db.insert_alert")
@patch("backend.mqtt_client.manager.broadcast_sync")
def test_sin_umbral_no_genera_alerta(mock_bs, mock_insert_alert, mock_threshold, mock_insert):
    mqtt_client.on_message(None, None, _make_mqtt_msg("SENSOR-NUEVO", value=999.0))

    mock_insert_alert.assert_not_called()
    assert mock_bs.call_count == 1


# ── 5. Observador NO recibe alerta biometrica via WS ─────────────────────────

def test_observador_no_recibe_alerta_biometrica_ws():
    ws_obs = _make_ws_mock()
    manager.connections[ws_obs] = "observador"
    try:
        _run_broadcast({
            "type": "alert",
            "sensor_id": "HR-01",
            "value": 200.0,
            "threshold_excedido": "max",
            "valor_min": 40.0,
            "valor_max": 180.0,
            "timestamp": "2026-09-24T20:15:00Z",
            "severidad": "critico",
        })
        ws_obs.send_text.assert_not_called()
    finally:
        manager.connections.pop(ws_obs, None)


# ── 6. Observador SI recibe alerta de sensor tecnico via WS ──────────────────

def test_observador_recibe_alerta_tecnica_ws():
    ws_obs = _make_ws_mock()
    manager.connections[ws_obs] = "observador"
    try:
        _run_broadcast({
            "type": "alert",
            "sensor_id": "TEMP-01",
            "value": 55.0,
            "threshold_excedido": "max",
            "valor_min": -10.0,
            "valor_max": 50.0,
            "timestamp": "2026-09-24T20:15:00Z",
            "severidad": "advertencia",
        })
        ws_obs.send_text.assert_called_once()
        sent = json.loads(ws_obs.send_text.call_args[0][0])
        assert sent["type"] == "alert"
        assert sent["sensor_id"] == "TEMP-01"
    finally:
        manager.connections.pop(ws_obs, None)


# ── 7. Administrador y control_mision reciben alertas biometricas ─────────────

@pytest.mark.parametrize("rol", ["administrador", "control_mision"])
def test_rol_privilegiado_recibe_alerta_biometrica_ws(rol):
    ws = _make_ws_mock()
    manager.connections[ws] = rol
    try:
        _run_broadcast({
            "type": "alert",
            "sensor_id": "HR-01",
            "value": 200.0,
            "threshold_excedido": "max",
            "valor_min": 40.0,
            "valor_max": 180.0,
            "timestamp": "2026-09-24T20:15:00Z",
            "severidad": "critico",
        })
        ws.send_text.assert_called_once()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["sensor_id"] == "HR-01"
    finally:
        manager.connections.pop(ws, None)


# ── 8. GET /alerts/active filtra biometricos para observador ──────────────────

@patch("backend.auth.get_user_by_username")
@patch("backend.db.get_active_alerts", return_value=[_ALERT_TEMP, _ALERT_HR])
def test_observador_no_recibe_alertas_biometricas_rest(mock_get_alerts, mock_get_user):
    mock_get_user.return_value = _mock_db_user("observador")
    token = _token_for("observador")
    response = client.get("/alerts/active", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    sensor_ids = [a["sensor_id"] for a in data]
    assert "HR-01" not in sensor_ids
    assert "TEMP-01" in sensor_ids


# ── 9. GET /alerts/active para administrador devuelve todo ────────────────────

@patch("backend.auth.get_user_by_username")
@patch("backend.db.get_active_alerts", return_value=[_ALERT_TEMP, _ALERT_HR])
def test_admin_recibe_todas_las_alertas_rest(mock_get_alerts, mock_get_user):
    mock_get_user.return_value = _mock_db_user("administrador")
    token = _token_for("administrador")
    response = client.get("/alerts/active", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    sensor_ids = [a["sensor_id"] for a in data]
    assert "HR-01" in sensor_ids
    assert "TEMP-01" in sensor_ids


# ── 10. Administrador puede actualizar umbral via REST ────────────────────────

@patch("backend.auth.get_user_by_username")
@patch("backend.db.upsert_threshold")
def test_admin_puede_actualizar_umbral(mock_upsert, mock_get_user):
    mock_get_user.return_value = _mock_db_user("administrador")
    mock_upsert.return_value = {
        "sensor_id": "TEMP-01",
        "valor_min": 0.0,
        "valor_max": 40.0,
        "actualizado_por": "administrador",
        "actualizado_en": datetime(2026, 9, 24, 20, 0, 0, tzinfo=timezone.utc),
    }
    token = _token_for("administrador")
    response = client.put(
        "/admin/thresholds/TEMP-01",
        json={"valor_min": 0.0, "valor_max": 40.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["sensor_id"] == "TEMP-01"
    assert data["valor_min"] == 0.0
    assert data["valor_max"] == 40.0
    mock_upsert.assert_called_once_with(
        sensor_id="TEMP-01", valor_min=0.0, valor_max=40.0, actualizado_por="administrador"
    )


# ── 11. Observador recibe 403 en PUT /admin/thresholds ───────────────────────

@patch("backend.auth.get_user_by_username")
def test_observador_403_en_update_threshold(mock_get_user):
    mock_get_user.return_value = _mock_db_user("observador")
    token = _token_for("observador")
    response = client.put(
        "/admin/thresholds/TEMP-01",
        json={"valor_min": 0.0, "valor_max": 40.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# ── 12. Integracion: nuevo umbral afecta a la siguiente lectura ───────────────

@patch("backend.mqtt_client.db.insert_reading")
@patch("backend.mqtt_client.db.get_active_alert", return_value=None)
@patch("backend.mqtt_client.db.insert_alert")
@patch("backend.mqtt_client.manager.broadcast_sync")
def test_nuevo_umbral_afecta_siguiente_lectura(mock_bs, mock_insert_alert, mock_get_active, mock_insert):
    """
    Simula que el umbral de TEMP-01 se actualiza a max=30 y que una lectura
    de 35 (antes valida con max=50) ahora genera alerta.
    """
    umbral_nuevo = {"sensor_id": "TEMP-01", "valor_min": -10.0, "valor_max": 30.0}

    with patch("backend.mqtt_client.db.get_threshold", return_value=umbral_nuevo):
        mock_insert_alert.return_value = {
            "id": 10, "sensor_id": "TEMP-01", "value": 35.0,
            "threshold_excedido": "max", "valor_min": -10.0, "valor_max": 30.0,
            "timestamp": datetime(2026, 9, 24, 20, 15, tzinfo=timezone.utc),
            "severidad": "advertencia", "resuelto": False,
            "visto_por_ultima_vez": None, "resuelto_en": None, "resuelto_por": None,
        }
        mqtt_client.on_message(None, None, _make_mqtt_msg("TEMP-01", value=35.0))

    mock_insert_alert.assert_called_once()
    assert mock_insert_alert.call_args.kwargs["threshold_excedido"] == "max"
    assert mock_insert_alert.call_args.kwargs["valor_max"] == 30.0

    alert_broadcast = mock_bs.call_args_list[1][0][0]
    assert alert_broadcast["type"] == "alert"
    assert alert_broadcast["valor_max"] == 30.0


# ── 13. PUT con valor_min >= valor_max devuelve 422 ───────────────────────────

@patch("backend.auth.get_user_by_username")
def test_update_threshold_invalido_422(mock_get_user):
    mock_get_user.return_value = _mock_db_user("administrador")
    token = _token_for("administrador")
    response = client.put(
        "/admin/thresholds/TEMP-01",
        json={"valor_min": 50.0, "valor_max": 10.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


# ── 14. GET /admin/thresholds devuelve lista ─────────────────────────────────

@patch("backend.auth.get_user_by_username")
@patch("backend.db.get_all_thresholds", return_value=[
    {"sensor_id": "TEMP-01", "valor_min": -10.0, "valor_max": 50.0,
     "actualizado_por": "seed", "actualizado_en": None},
])
def test_admin_lista_thresholds(mock_all_thresholds, mock_get_user):
    mock_get_user.return_value = _mock_db_user("administrador")
    token = _token_for("administrador")
    response = client.get("/admin/thresholds", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["sensor_id"] == "TEMP-01"


# ── 15. Observador recibe 403 en GET /admin/thresholds ───────────────────────

@patch("backend.auth.get_user_by_username")
def test_observador_403_en_list_thresholds(mock_get_user):
    mock_get_user.return_value = _mock_db_user("observador")
    token = _token_for("observador")
    response = client.get("/admin/thresholds", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# CICLO DE VIDA — deduplicacion + resolucion
# ═══════════════════════════════════════════════════════════════════════════════

_ALERT_TEMP_ACTIVA = {
    "id": 42, "sensor_id": "TEMP-01", "value": 55.0,
    "threshold_excedido": "max", "valor_min": -10.0, "valor_max": 50.0,
    "timestamp": datetime(2026, 9, 24, 20, 15, 0, tzinfo=timezone.utc),
    "severidad": "advertencia", "resuelto": False,
    "visto_por_ultima_vez": datetime(2026, 9, 24, 20, 15, 0, tzinfo=timezone.utc),
    "resuelto_en": None, "resuelto_por": None,
}

_ALERT_TEMP_RESUELTA = {
    **_ALERT_TEMP_ACTIVA,
    "resuelto": True,
    "resuelto_en": datetime(2026, 9, 24, 20, 20, 0, tzinfo=timezone.utc),
    "resuelto_por": "control_mision",
}


# ── 16. Lecturas consecutivas fuera de rango actualizan la alerta existente ───

@patch("backend.mqtt_client.db.insert_reading")
@patch("backend.mqtt_client.db.get_threshold", return_value=_THRESHOLD_TEMP)
@patch("backend.mqtt_client.db.get_active_alert", return_value=_ALERT_TEMP_ACTIVA)
@patch("backend.mqtt_client.db.update_alert_value", return_value={**_ALERT_TEMP_ACTIVA, "value": 60.0})
@patch("backend.mqtt_client.db.insert_alert")
@patch("backend.mqtt_client.manager.broadcast_sync")
def test_lecturas_consecutivas_fuera_de_rango_no_duplican_alerta(
    mock_bs, mock_insert_alert, mock_update, mock_get_active, mock_threshold, mock_insert
):
    """Segunda lectura fuera del mismo rango actualiza la alerta existente, no crea una nueva."""
    mqtt_client.on_message(None, None, _make_mqtt_msg("TEMP-01", value=60.0))

    # No debe crear alerta nueva
    mock_insert_alert.assert_not_called()
    # Debe actualizar la existente con el id correcto
    mock_update.assert_called_once()
    assert mock_update.call_args[0][0] == 42     # alert_id
    assert mock_update.call_args[0][1] == 60.0   # nuevo value
    # El broadcast de alerta debe referirse a la alerta existente
    alert_broadcast = mock_bs.call_args_list[1][0][0]
    assert alert_broadcast["type"] == "alert"
    assert alert_broadcast["id"] == 42


# ── 17. Lectura que vuelve a rango resuelve la alerta automaticamente ─────────

@patch("backend.mqtt_client.db.insert_reading")
@patch("backend.mqtt_client.db.get_threshold", return_value=_THRESHOLD_TEMP)
@patch("backend.mqtt_client.db.resolve_alert", return_value={**_ALERT_TEMP_ACTIVA, "resuelto": True})
@patch("backend.mqtt_client.manager.broadcast_sync")
def test_lectura_en_rango_resuelve_alerta_activa(
    mock_bs, mock_resolve, mock_threshold, mock_insert
):
    """Lectura dentro de rango marca resuelto=True en la alerta activa del sensor."""
    # get_active_alert devuelve la alerta activa solo para "max", None para "min"
    def _get_active(sensor_id, excedido):
        return _ALERT_TEMP_ACTIVA if excedido == "max" else None

    with patch("backend.mqtt_client.db.get_active_alert", side_effect=_get_active):
        mqtt_client.on_message(None, None, _make_mqtt_msg("TEMP-01", value=25.0))

    mock_resolve.assert_called_once_with(42, resuelto_por=None)
    # Solo un broadcast (la lectura), no se emite alerta
    assert mock_bs.call_count == 1
    assert mock_bs.call_args[0][0]["type"] == "reading"


# ── 18. Tras auto-resolucion, nueva lectura fuera de rango crea alerta NUEVA ──

@patch("backend.mqtt_client.db.insert_reading")
@patch("backend.mqtt_client.db.get_threshold", return_value=_THRESHOLD_TEMP)
@patch("backend.mqtt_client.db.get_active_alert", return_value=None)   # ya no hay activa
@patch("backend.mqtt_client.db.insert_alert", return_value={**_ALERT_TEMP, "id": 99})
@patch("backend.mqtt_client.manager.broadcast_sync")
def test_nueva_alerta_tras_resolucion(
    mock_bs, mock_insert_alert, mock_get_active, mock_threshold, mock_insert
):
    """Si no hay alerta activa (fue resuelta), una nueva lectura fuera de rango crea una nueva."""
    mqtt_client.on_message(None, None, _make_mqtt_msg("TEMP-01", value=55.0))

    mock_insert_alert.assert_called_once()
    alert_broadcast = mock_bs.call_args_list[1][0][0]
    assert alert_broadcast["type"] == "alert"
    assert alert_broadcast["id"] == 99


# ── 19. PATCH /alerts/{id}/resolve marca alerta como resuelta manualmente ─────

@patch("backend.auth.get_user_by_username")
@patch("backend.db.get_alert_by_id", return_value=_ALERT_TEMP_ACTIVA)
@patch("backend.db.resolve_alert", return_value=_ALERT_TEMP_RESUELTA)
def test_patch_resolve_alerta_manualmente(mock_resolve, mock_get_alert, mock_get_user):
    mock_get_user.return_value = _mock_db_user("control_mision")
    token = _token_for("control_mision")
    response = client.patch(
        "/alerts/42/resolve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["resuelto"] is True
    assert data["resuelto_por"] == "control_mision"
    mock_resolve.assert_called_once_with(42, resuelto_por="control_mision")


# ── 20. Observador recibe 403 en PATCH /alerts/{id}/resolve ──────────────────

@patch("backend.auth.get_user_by_username")
def test_observador_403_en_resolve_alerta(mock_get_user):
    mock_get_user.return_value = _mock_db_user("observador")
    token = _token_for("observador")
    response = client.patch(
        "/alerts/42/resolve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# ── 21. PATCH sobre alerta ya resuelta devuelve 409 ──────────────────────────

@patch("backend.auth.get_user_by_username")
@patch("backend.db.get_alert_by_id", return_value=_ALERT_TEMP_RESUELTA)
def test_patch_resolve_alerta_ya_resuelta_409(mock_get_alert, mock_get_user):
    mock_get_user.return_value = _mock_db_user("administrador")
    token = _token_for("administrador")
    response = client.patch(
        "/alerts/42/resolve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


# ── 22. PATCH sobre alerta inexistente devuelve 404 ──────────────────────────

@patch("backend.auth.get_user_by_username")
@patch("backend.db.get_alert_by_id", return_value=None)
def test_patch_resolve_alerta_inexistente_404(mock_get_alert, mock_get_user):
    mock_get_user.return_value = _mock_db_user("administrador")
    token = _token_for("administrador")
    response = client.patch(
        "/alerts/9999/resolve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
