"""
Backend FastAPI — Mision Atabey Telemetria.

Startup:
  1. Crea tablas readings, users, thresholds, alerts y locations en PostgreSQL; seeds.
  2. Conecta al broker MQTT con suscripcion wildcard atabey/#.

Endpoints publicos:
  POST /auth/login                 — emite JWT con claim de rol
  GET  /health

Endpoints autenticados (cualquier rol):
  GET  /readings/latest?sensor_id=...
  GET  /locations/latest?device_id=...
  GET  /alerts/active              — alertas activas (filtrado biometrico por rol)
  WS   /ws/readings?token=...      — filtra biometricos para observador; emite reading/alert/location

Endpoints de operador (administrador o control_mision):
  PATCH /alerts/{id}/resolve       — resolucion manual de alerta

Endpoints de administracion (solo administrador):
  GET    /admin/users
  POST   /admin/users
  DELETE /admin/users/{user_id}
  GET    /admin/thresholds
  PUT    /admin/thresholds/{sensor_id}
"""

import logging
import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm

import backend.db as db
import backend.mqtt_client as mqtt_client
from backend.models import (
    AlertPublic,
    AuthMode,
    BatchAck,
    IngestRecord,
    IngestSummary,
    LocationPublic,
    ReadingBatch,
    SensorCatalogResponse,
    Threshold,
    ThresholdUpdate,
    Token,
    TripulanteMeta,
    User,
    UserCreate,
    UserPublic,
)
from backend.auth import (
    DEFAULT_ROL,
    DEFAULT_USERNAME,
    REQUIRE_LOGIN,
    authenticate_user,
    create_access_token,
    get_current_user,
    get_password_hash,
    get_user_from_token,
    require_role,
)
from backend.ws_manager import BIOMETRIC_SENSORS, manager
import backend.catalog as catalog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def _build_cors_origins() -> list[str]:
    """
    Orígenes permitidos para el dashboard.

    `CORS_ORIGINS` (env) = lista separada por comas. Si contiene `*`, se permiten
    todos los orígenes (necesario cuando el dashboard vive en un dominio
    público). En modo anónimo y sin `CORS_ORIGINS` explicito, se abre `*`
    porque el acceso es publico de todas formas.
    """
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    if not REQUIRE_LOGIN:
        return ["*"]
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


_cors_origins = _build_cors_origins()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando backend Atabey...")
    db.create_table()
    manager.set_loop(asyncio.get_running_loop())
    mqtt_client.start()
    yield
    logger.info("Deteniendo backend Atabey...")
    mqtt_client.stop()


app = FastAPI(
    title="Atabey Telemetria",
    description="Backend de telemetria para Mision Atabey 1.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials="*" not in _cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username, "rol": user.rol})
    return {"access_token": access_token, "token_type": "bearer"}


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/readings")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    # En modo anonimo (REQUIRE_LOGIN=false) el token es opcional y se usa el
    # rol por defecto. El filtrado por rol del manager sigue igual.
    if REQUIRE_LOGIN:
        user = get_user_from_token(token) if token else None
        if not user:
            await websocket.close(code=1008)
            return
        rol = user.rol
    else:
        user = get_user_from_token(token) if token else None
        rol = user.rol if user else DEFAULT_ROL

    await manager.connect(websocket, rol)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ── Telemetria (cualquier rol autenticado) ────────────────────────────────────

@app.get("/readings/latest", summary="Ultima lectura de un sensor")
def get_latest_reading(
    sensor_id: str = Query(..., description="ID del sensor, ej. TEMP-01"),
    current_user: User = Depends(get_current_user),
):
    if sensor_id in BIOMETRIC_SENSORS and current_user.rol == "observador":
        raise HTTPException(
            status_code=403,
            detail="Los datos biometricos son de acceso restringido.",
        )
    reading = db.get_latest_reading(sensor_id)
    if reading is None:
        raise HTTPException(
            status_code=404,
            detail=f"No hay lecturas para sensor_id={sensor_id!r}",
        )
    return reading


# ── Buffer de datos + ACK ────────────────────────────────────────────────────

@app.post(
    "/readings/batch",
    response_model=BatchAck,
    summary="Recibe un buffer de datos y devuelve el ACK de confirmacion",
)
def ingest_reading_batch(
    batch: ReadingBatch,
    current_user: User = Depends(get_current_user),
):
    """
    Recibe un BUFFER DE DATOS (lote de lecturas) del ESP32 / firmware.

    Guarda todas las lecturas en una transaccion y devuelve un ACK item por
    item: que sensor llego, en que momento se guardo y con que id quedo en la
    base de datos. Si el `buffer_id` ya se habia recibido, no duplica nada y
    devuelve el ACK original (idempotencia).

    El mismo ACK se publica por MQTT en `atabey/ack/{device_id}` para que el
    emisor confirme la llegada sin depender de HTTP.
    """
    ack = mqtt_client.ingest_batch(batch)
    mqtt_client.publish_ack(ack)
    logger.info(
        "ACK HTTP buffer %s (%s): %d aceptadas, %d duplicadas, %d rechazadas",
        ack.buffer_id, ack.device_id, ack.accepted, ack.duplicates, ack.rejected,
    )
    return ack


@app.get(
    "/sensors/catalog",
    response_model=SensorCatalogResponse,
    summary="Catalogo canonico de variables de sensores",
)
def get_sensors_catalog(current_user: User = Depends(get_current_user)):
    """
    Devuelve el catalogo completo de variables que puede enviar el hardware:
    `sensor_id`, nombre de la variable, unidad, grupo, hardware de referencia,
    rango y umbral. Incluye los contratos de lectura, buffer, ACK y MQTT.

    Esta es la referencia que usa el firmware/Vantroi para armar buffers validos.
    """
    return catalog.catalog_summary()


@app.get(
    "/ingest/recent",
    response_model=IngestSummary,
    summary="Registro de ingesta: que se guardo, de que sensor y cuando",
)
def get_recent_ingest(
    limit: int = Query(100, ge=1, le=1000, description="Numero de registros a devolver"),
    current_user: User = Depends(get_current_user),
):
    """
    Registro de lo que el servidor ha guardado: de que sensor vino cada dato,
    cuando lo midio el sensor (`timestamp`) y cuando se guardo aqui
    (`received_at`). Cada registro pertenece a un `buffer_id` (envio).
    """
    rows = db.get_recent_ingest(limit)

    # Agrupar por buffer para ver los envios completos.
    buffers: dict[str, dict] = {}
    for row in rows:
        buffer_id = row.get("buffer_id")
        if buffer_id is None:
            continue
        entry = buffers.setdefault(buffer_id, {
            "buffer_id": buffer_id,
            "device_id": row["device_id"],
            "received_at": row["received_at"].isoformat(),
            "readings": 0,
            "sensors": [],
        })
        entry["readings"] += 1
        entry["sensors"].append(row["sensor_id"])

    return IngestSummary(
        total=len(rows),
        generated_at=datetime.now(timezone.utc),
        buffers=list(buffers.values()),
        records=[IngestRecord(**row) for row in rows],
    )


@app.get(
    "/auth/mode",
    response_model=AuthMode,
    summary="Modo de autenticacion activo",
)
def get_auth_mode():
    """
    Informa al frontend si debe mostrar la pantalla de login.

    Con `requires_login=false` el dashboard entra directo con el rol por
    defecto (modo de pruebas con sensores formales).
    """
    return AuthMode(
        requires_login=REQUIRE_LOGIN,
        default_rol=DEFAULT_ROL,
        default_username=DEFAULT_USERNAME,
    )


# ── Posicion del tripulante (cualquier rol autenticado) ───────────────────────

@app.get(
    "/locations/latest",
    response_model=LocationPublic,
    summary="Ultima posicion GPS de un tripulante",
)
def get_latest_location(
    device_id: str = Query(..., description="ID del dispositivo, ej. EVA-01"),
    current_user: User = Depends(get_current_user),
):
    """
    Devuelve la posicion mas reciente de un tripulante.
    Acceso para cualquier rol autenticado — la posicion no es dato biometrico.
    """
    location = db.get_latest_location(device_id)
    if location is None:
        raise HTTPException(
            status_code=404,
            detail=f"No hay posiciones registradas para device_id={device_id!r}",
        )
    return location


@app.get(
    "/tripulantes",
    response_model=list[TripulanteMeta],
    summary="Metadata de tripulantes conocidos (device_id, sexo)",
)
def list_tripulantes(current_user: User = Depends(get_current_user)):
    """
    Devuelve la metadata visible de cada tripulante conocido (sexo, etc.).
    Acceso para cualquier rol autenticado — uso puramente visual en el mapa.
    """
    return db.get_tripulantes_meta()


# ── Alertas activas (cualquier rol autenticado, filtrado biometrico) ──────────

@app.get(
    "/alerts/active",
    response_model=list[AlertPublic],
    summary="Alertas activas (no resueltas)",
)
def get_active_alerts(current_user: User = Depends(get_current_user)):
    """
    Devuelve alertas activas.
    Observador no ve alertas de sensores biometricos (mismo criterio que /readings/latest).
    """
    alerts = db.get_active_alerts()
    if current_user.rol == "observador":
        alerts = [a for a in alerts if a["sensor_id"] not in BIOMETRIC_SENSORS]
    return alerts


@app.patch(
    "/alerts/{alert_id}/resolve",
    response_model=AlertPublic,
    summary="Resuelve una alerta manualmente",
)
def resolve_alert(
    alert_id: int,
    current_user: User = Depends(require_role("administrador", "control_mision")),
):
    """
    Marca la alerta como resuelta manualmente.
    Solo accesible para administrador y control_mision.
    """
    alert = db.get_alert_by_id(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alerta no encontrada.")
    if alert["resuelto"]:
        raise HTTPException(status_code=409, detail="La alerta ya esta resuelta.")
    resolved = db.resolve_alert(alert_id, resuelto_por=current_user.username)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Alerta no encontrada.")
    return resolved


# ── Administración de usuarios (solo administrador) ───────────────────────────

@app.get(
    "/admin/users",
    response_model=list[UserPublic],
    dependencies=[Depends(require_role("administrador"))],
    summary="Lista todos los usuarios",
)
def list_users():
    return db.get_all_users()


@app.post(
    "/admin/users",
    response_model=UserPublic,
    status_code=201,
    dependencies=[Depends(require_role("administrador"))],
    summary="Crea un nuevo usuario",
)
def create_user(payload: UserCreate):
    password_hash = get_password_hash(payload.password)
    try:
        return db.create_user(payload.username, password_hash, payload.rol)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete(
    "/admin/users/{user_id}",
    status_code=204,
    dependencies=[Depends(require_role("administrador"))],
    summary="Elimina un usuario por ID",
)
def delete_user(user_id: int):
    if not db.delete_user(user_id):
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")


# ── Administración de umbrales (solo administrador) ───────────────────────────

@app.get(
    "/admin/thresholds",
    response_model=list[Threshold],
    dependencies=[Depends(require_role("administrador"))],
    summary="Lista todos los umbrales configurados",
)
def list_thresholds():
    return db.get_all_thresholds()


@app.put(
    "/admin/thresholds/{sensor_id}",
    response_model=Threshold,
    dependencies=[Depends(require_role("administrador"))],
    summary="Crea o actualiza el umbral de un sensor",
)
def update_threshold(
    sensor_id: str,
    payload: ThresholdUpdate,
    current_user: User = Depends(require_role("administrador")),
):
    if payload.valor_min >= payload.valor_max:
        raise HTTPException(
            status_code=422,
            detail="valor_min debe ser menor que valor_max.",
        )
    return db.upsert_threshold(
        sensor_id=sensor_id,
        valor_min=payload.valor_min,
        valor_max=payload.valor_max,
        actualizado_por=current_user.username,
    )


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", summary="Health check")
def health():
    return {"status": "ok"}
