"""
Tests del modulo 6 — roles y control de acceso.

Cubren (sin Docker, todo mockeado):
1. JWT emitido en login trae el claim 'rol' correcto para cada uno de los tres roles.
2. Creacion de usuario con rol via endpoint de administrador (POST /admin/users).
3. 403 para observador en ese endpoint.
4. Filtrado de biometricos en el WS para observador: se verifica directamente
   sobre manager.broadcast (logica de filtrado) y sobre el endpoint REST.
5. Administrador y control_mision reciben biometricos (via manager.broadcast).
6. Observador recibe sensores tecnicos (via manager.broadcast).
7. Observador recibe 403 al pedir /readings/latest?sensor_id=HR-01.
8. Observador puede pedir /readings/latest?sensor_id=TEMP-01 (tecnico).
9. JWT emitido en /auth/login trae claim 'rol' para los tres roles.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.ws_manager import BIOMETRIC_SENSORS, manager

client = TestClient(app)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_user(rol: str):
    from backend.models import User
    return User(id=1, username=rol, rol=rol)


def _token_for(rol: str) -> str:
    from backend.auth import create_access_token
    return create_access_token(data={"sub": rol, "rol": rol})


def _mock_db_user(rol: str):
    from passlib.context import CryptContext
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return {
        "id": 1,
        "username": rol,
        "password_hash": ctx.hash("pass"),
        "rol": rol,
    }


def _run_broadcast(msg: dict) -> None:
    """Corre manager.broadcast sincrónicamente en un loop temporal."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(manager.broadcast(msg))
    finally:
        loop.close()


# ── 1. JWT contiene claim 'rol' para cada rol ─────────────────────────────────

@pytest.mark.parametrize("rol", ["administrador", "control_mision", "observador"])
def test_jwt_contiene_claim_rol(rol):
    from jose import jwt as jose_jwt
    from backend.auth import SECRET_KEY, ALGORITHM
    token = _token_for(rol)
    payload = jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["rol"] == rol


# ── 2. Administrador puede crear usuario ──────────────────────────────────────

@patch("backend.auth.get_user_by_username")
@patch("backend.db.create_user")
def test_admin_puede_crear_usuario(mock_create, mock_get_user):
    mock_get_user.return_value = _mock_db_user("administrador")
    mock_create.return_value = {"id": 99, "username": "nuevo", "rol": "observador"}

    token = _token_for("administrador")
    response = client.post(
        "/admin/users",
        json={"username": "nuevo", "password": "pass123", "rol": "observador"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["rol"] == "observador"


# ── 3. Observador recibe 403 en /admin/users ──────────────────────────────────

@patch("backend.auth.get_user_by_username")
def test_observador_403_en_admin_users_get(mock_get_user):
    mock_get_user.return_value = _mock_db_user("observador")
    token = _token_for("observador")
    response = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@patch("backend.auth.get_user_by_username")
def test_observador_403_en_admin_users_post(mock_get_user):
    mock_get_user.return_value = _mock_db_user("observador")
    token = _token_for("observador")
    response = client.post(
        "/admin/users",
        json={"username": "x", "password": "y", "rol": "observador"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# ── 4-6. Filtrado WS via manager.broadcast ───────────────────────────────────
#
# Se testea manager.broadcast directamente con WebSocket mockeados.
# Esto evita las limitaciones del TestClient de Starlette con receive_json()
# y verifica la logica de filtrado sin ambiguedad.

def _make_ws_mock():
    """WebSocket mock con send_text como AsyncMock."""
    ws = MagicMock()
    ws.send_text = AsyncMock()
    return ws


# ── 4. Observador NO recibe biometrico por WS ─────────────────────────────────

def test_observador_no_recibe_biometrico_ws():
    """manager.broadcast NO entrega HR-01 a una conexion con rol observador."""
    ws_obs = _make_ws_mock()
    manager.connections[ws_obs] = "observador"
    try:
        _run_broadcast({
            "device_id": "EVA-01",
            "sensor_id": "HR-01",
            "timestamp": "2026-09-24T20:15:00Z",
            "value": 80.0,
            "unit": "bpm",
            "sequence": 1,
        })
        ws_obs.send_text.assert_not_called()
    finally:
        manager.connections.pop(ws_obs, None)


# ── 5. Administrador SI recibe biometrico por WS ──────────────────────────────

def test_admin_recibe_biometrico_ws():
    """manager.broadcast entrega HR-01 a una conexion con rol administrador."""
    ws_admin = _make_ws_mock()
    manager.connections[ws_admin] = "administrador"
    try:
        _run_broadcast({
            "device_id": "EVA-01",
            "sensor_id": "HR-01",
            "timestamp": "2026-09-24T20:15:00Z",
            "value": 80.0,
            "unit": "bpm",
            "sequence": 2,
        })
        ws_admin.send_text.assert_called_once()
        sent = json.loads(ws_admin.send_text.call_args[0][0])
        assert sent["sensor_id"] == "HR-01"
    finally:
        manager.connections.pop(ws_admin, None)


# ── 5b. Control de mision SI recibe biometrico por WS ────────────────────────

def test_control_mision_recibe_biometrico_ws():
    """manager.broadcast entrega SPO2-01 a control_mision."""
    ws_mc = _make_ws_mock()
    manager.connections[ws_mc] = "control_mision"
    try:
        _run_broadcast({
            "device_id": "EVA-01",
            "sensor_id": "SPO2-01",
            "timestamp": "2026-09-24T20:15:00Z",
            "value": 98.0,
            "unit": "%",
            "sequence": 3,
        })
        ws_mc.send_text.assert_called_once()
        sent = json.loads(ws_mc.send_text.call_args[0][0])
        assert sent["sensor_id"] == "SPO2-01"
    finally:
        manager.connections.pop(ws_mc, None)


# ── 6. Observador recibe sensor tecnico por WS ────────────────────────────────

def test_observador_recibe_sensor_tecnico_ws():
    """manager.broadcast entrega TEMP-01 a observador (no es biometrico)."""
    ws_obs = _make_ws_mock()
    manager.connections[ws_obs] = "observador"
    try:
        _run_broadcast({
            "device_id": "ESP32-01",
            "sensor_id": "TEMP-01",
            "timestamp": "2026-09-24T20:15:00Z",
            "value": 25.0,
            "unit": "C",
            "sequence": 4,
        })
        ws_obs.send_text.assert_called_once()
        sent = json.loads(ws_obs.send_text.call_args[0][0])
        assert sent["sensor_id"] == "TEMP-01"
    finally:
        manager.connections.pop(ws_obs, None)


# ── 6b. Verificacion de los tres sensores biometricos para observador ─────────

@pytest.mark.parametrize("sensor_id", sorted(BIOMETRIC_SENSORS))
def test_observador_no_recibe_ninguno_de_los_tres_biometricos(sensor_id):
    """BTEMP-01, HR-01 y SPO2-01 nunca llegan a observador."""
    ws_obs = _make_ws_mock()
    manager.connections[ws_obs] = "observador"
    try:
        _run_broadcast({
            "device_id": "EVA-01",
            "sensor_id": sensor_id,
            "timestamp": "2026-09-24T20:15:00Z",
            "value": 1.0,
            "unit": "x",
            "sequence": 99,
        })
        ws_obs.send_text.assert_not_called()
    finally:
        manager.connections.pop(ws_obs, None)


# ── 7. Observador recibe 403 en /readings/latest para sensor biometrico ───────

@patch("backend.auth.get_user_by_username")
def test_observador_403_en_readings_biometrico(mock_get_user):
    mock_get_user.return_value = _mock_db_user("observador")
    token = _token_for("observador")
    response = client.get(
        "/readings/latest?sensor_id=HR-01",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# ── 8. Observador puede pedir sensor tecnico por REST ─────────────────────────

@patch("backend.auth.get_user_by_username")
@patch("backend.db.get_latest_reading")
def test_observador_puede_pedir_sensor_tecnico_rest(mock_get_latest, mock_get_user):
    mock_get_user.return_value = _mock_db_user("observador")
    mock_get_latest.return_value = {
        "device_id": "ESP32-01", "sensor_id": "TEMP-01",
        "timestamp": "2026-09-24T20:15:00+00:00",
        "value": 25.0, "unit": "C", "sequence": 1,
    }
    token = _token_for("observador")
    response = client.get(
        "/readings/latest?sensor_id=TEMP-01",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["sensor_id"] == "TEMP-01"


# ── 9. JWT en /auth/login trae claim 'rol' ────────────────────────────────────

@pytest.mark.parametrize("rol,username,password", [
    ("administrador", "admin", "admin_pass"),
    ("control_mision", "mision", "mision_pass"),
    ("observador", "observador", "observador_pass"),
])
def test_login_jwt_claim_rol(rol, username, password):
    """El token devuelto por /auth/login lleva el claim 'rol' correcto."""
    from passlib.context import CryptContext
    from jose import jwt as jose_jwt
    from backend.auth import SECRET_KEY, ALGORITHM

    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    mock_user = {
        "id": 1,
        "username": username,
        "password_hash": ctx.hash(password),
        "rol": rol,
    }

    with patch("backend.auth.get_user_by_username", return_value=mock_user):
        response = client.post(
            "/auth/login",
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    assert response.status_code == 200
    token = response.json()["access_token"]
    payload = jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["rol"] == rol


# ═══════════════════════════════════════════════════════════════════════════════
# Modulo 10 — validacion de rol con Literal + regresion de migracion
# ═══════════════════════════════════════════════════════════════════════════════

# ── 10. POST /admin/users con rol invalido devuelve 422 ───────────────────────

@pytest.mark.parametrize("rol_invalido", [
    "Administrador",   # mayuscula — el bug real que encontramos
    "ADMIN",
    "superusuario",
    "admin",           # abreviacion incorrecta
    "",                # vacio
    "Control_Mision",  # variante con mayuscula
])
@patch("backend.auth.get_user_by_username")
def test_rol_invalido_en_create_user_devuelve_422(mock_get_user, rol_invalido):
    """POST /admin/users con un rol fuera de los tres valores permitidos devuelve 422."""
    mock_get_user.return_value = _mock_db_user("administrador")
    token = _token_for("administrador")
    response = client.post(
        "/admin/users",
        json={"username": "test", "password": "pass", "rol": rol_invalido},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422, (
        f"Se esperaba 422 para rol={rol_invalido!r}, "
        f"pero se obtuvo {response.status_code}"
    )


# ── 11. POST /admin/users con los tres roles validos sigue funcionando ────────

@pytest.mark.parametrize("rol_valido", [
    "administrador",
    "control_mision",
    "observador",
])
@patch("backend.auth.get_user_by_username")
@patch("backend.db.create_user")
def test_rol_valido_en_create_user_devuelve_201(mock_create, mock_get_user, rol_valido):
    """POST /admin/users con un rol valido sigue devolviendo 201."""
    mock_get_user.return_value = _mock_db_user("administrador")
    mock_create.return_value = {"id": 99, "username": "test", "rol": rol_valido}
    token = _token_for("administrador")
    response = client.post(
        "/admin/users",
        json={"username": "test", "password": "pass", "rol": rol_valido},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["rol"] == rol_valido


# ── 12. Regresion: la migracion normaliza roles legacy con mayuscula ──────────

def test_migracion_normaliza_rol_con_mayuscula():
    """
    Regresion del bug real: un usuario con rol='Administrador' (mayuscula)
    debe quedar con rol='administrador' tras correr la logica de normalizacion.

    Se simula directamente la logica SQL de normalizacion sin tocar la BD real,
    verificando que la condicion de deteccion y el valor esperado son correctos.
    """
    # Estos son los tres casos que cubrimos en la migracion
    casos = [
        # (rol_entrada,        rol_esperado_tras_migracion)
        ("Administrador",   "administrador"),   # mayuscula inicial — bug real
        ("ADMINISTRADOR",   "administrador"),   # todo mayusculas
        ("Observador",      "observador"),      # mayuscula inicial
        ("Control_mision",  "control_mision"),  # mayuscula inicial
        ("Control_Mision",  "control_mision"),  # mayusculas mixtas
        ("administrador",   "administrador"),   # ya correcto — no cambia
        ("control_mision",  "control_mision"),  # ya correcto — no cambia
        ("observador",      "observador"),      # ya correcto — no cambia
    ]

    def _normalize(rol: str) -> str:
        """Replica la logica de la migracion SQL en Python."""
        mapping = {
            "administrador":  "administrador",
            "control_mision": "control_mision",
            "observador":     "observador",
        }
        lower = rol.lower()
        if lower in mapping and rol != mapping[lower]:
            return mapping[lower]
        return rol  # sin cambio

    for rol_entrada, rol_esperado in casos:
        resultado = _normalize(rol_entrada)
        assert resultado == rol_esperado, (
            f"Migracion fallo para '{rol_entrada}': "
            f"resultado='{resultado}', esperado='{rol_esperado}'"
        )


# ── 13. UserCreate rechaza rol invalido a nivel de modelo Pydantic ────────────

def test_usercreate_rechaza_rol_invalido():
    """Validacion a nivel de modelo: UserCreate debe lanzar error para roles invalidos."""
    from pydantic import ValidationError
    from backend.models import UserCreate

    with pytest.raises(ValidationError):
        UserCreate(username="test", password="pass", rol="Administrador")

    with pytest.raises(ValidationError):
        UserCreate(username="test", password="pass", rol="superusuario")


def test_usercreate_acepta_roles_validos():
    """UserCreate acepta los tres roles validos exactos."""
    from backend.models import UserCreate

    for rol in ("administrador", "control_mision", "observador"):
        u = UserCreate(username="test", password="pass", rol=rol)
        assert u.rol == rol
