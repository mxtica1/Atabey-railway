"""
Modelos Pydantic para Mision Atabey.

SensorReading representa el contrato de datos exacto definido en AGENTS.md.
No modificar los campos sin acuerdo del equipo de hardware.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class SensorReading(BaseModel):
    """Lectura de un sensor segun el contrato de datos de Mision Atabey."""

    device_id: str
    sensor_id: str
    timestamp: datetime
    value: float
    unit: str
    sequence: int

    model_config = {"extra": "ignore"}  # campos extra en el JSON se ignoran


# ── Buffer de datos + ACK ───────────────────────────────────────────────────
#
# Un "buffer" es un lote de lecturas que el ESP32/firmware acumula y envia
# de una vez. El servidor confirma cada item con un ACK para que el emisor
# sepa que llego y de que sensor.

class ReadingBatch(BaseModel):
    """
    Buffer de datos enviado por el ESP32 / firmware.

    El campo `buffer_id` es la clave de idempotencia: si el mismo buffer_id
    se reenvia, el servidor lo detecta y responde con el ACK original sin
    duplicar las lecturas.
    """

    device_id: str
    buffer_id: str
    sent_at: Optional[datetime] = None
    readings: list[SensorReading] = Field(..., min_length=1, description="Al menos una lectura")

    model_config = {"extra": "ignore"}


class BatchItemAck(BaseModel):
    """Confirmacion de UNA lectura dentro del buffer."""

    sensor_id: str
    sequence: int
    status: Literal["stored", "duplicate", "rejected"]
    received_at: Optional[datetime] = None
    db_id: Optional[int] = None
    error: Optional[str] = None


class BatchAck(BaseModel):
    """
    Confirmacion (ACK) del servidor: el buffer llego y quedo guardado.
    Se devuelve por HTTP y se publica por MQTT en `atabey/ack/{device_id}`.
    """

    type: Literal["ack"] = "ack"
    device_id: str
    buffer_id: str
    received_at: datetime
    accepted: int
    rejected: int
    duplicates: int
    items: list[BatchItemAck]


class Token(BaseModel):
    """Respuesta de login con el token JWT."""
    access_token: str
    token_type: str


class LoginRequest(BaseModel):
    """Peticion de login."""
    username: str
    password: str


class User(BaseModel):
    """Representa a un usuario en el sistema (sin password_hash)."""
    id: int
    username: str
    rol: str


class UserCreate(BaseModel):
    """Payload para crear un nuevo usuario (solo administrador)."""
    username: str
    password: str
    rol: Literal["administrador", "control_mision", "observador"]


class UserPublic(BaseModel):
    """Representacion publica de un usuario (sin hash)."""
    id: int
    username: str
    rol: Literal["administrador", "control_mision", "observador"]


# ── Umbrales ──────────────────────────────────────────────────────────────────

class Threshold(BaseModel):
    """Umbral de alerta para un sensor."""
    sensor_id: str
    valor_min: float
    valor_max: float
    actualizado_por: Optional[str] = None
    actualizado_en: Optional[datetime] = None


class ThresholdUpdate(BaseModel):
    """Payload para actualizar un umbral via REST."""
    valor_min: float
    valor_max: float


# ── Alertas ───────────────────────────────────────────────────────────────────

class AlertPublic(BaseModel):
    """Representacion publica de una alerta."""
    id: int
    sensor_id: str
    value: float
    threshold_excedido: Literal["min", "max"]
    valor_min: float
    valor_max: float
    timestamp: datetime
    severidad: str
    resuelto: bool
    visto_por_ultima_vez: Optional[datetime] = None
    resuelto_en: Optional[datetime] = None
    resuelto_por: Optional[str] = None


# ── Coordenadas del tripulante ────────────────────────────────────────────────

class LocationUpdate(BaseModel):
    """
    Posicion GPS de un tripulante.
    Entidad separada de SensorReading — una coordenada es un par (lat, lon),
    no un escalar, y tiene semantica distinta al pipeline de sensores.

    `sexo` es opcional y puramente visual (color del marcador en el mapa).
    No se filtra por rol, no afecta el pipeline de alertas.
    """
    device_id: str
    timestamp: datetime
    lat: float
    lon: float
    sequence: int
    sexo: Optional[Literal["M", "F"]] = None

    model_config = {"extra": "ignore"}


class LocationPublic(BaseModel):
    """Representacion publica de una posicion."""
    id: int
    device_id: str
    timestamp: datetime
    lat: float
    lon: float
    sequence: int
    sexo: Optional[Literal["M", "F"]] = None


class TripulanteMeta(BaseModel):
    """Metadata visible del tripulante (id, sexo)."""
    device_id: str
    sexo: Optional[Literal["M", "F"]] = None


# ── Catalogo de sensores ──────────────────────────────────────────────────────

class ThresholdRange(BaseModel):
    """Rango de umbral (sin metadatos de auditoria) para el catalogo."""
    valor_min: float
    valor_max: float


class SensorCatalogEntry(BaseModel):
    """Una variable del catalogo canonico de sensores."""
    sensor_id: str
    variable: str
    nombre: str
    unit: str
    group: str
    description: str
    hardware: str
    biometrico: bool
    value_min: float
    value_max: float
    threshold: Optional[ThresholdRange] = None
    device_id: str


class SensorCatalogDevice(BaseModel):
    """Agrupacion de sensores por dispositivo."""
    device_id: str
    sensor_count: int
    groups: list[str]
    sensors: list[SensorCatalogEntry]


class SensorCatalogResponse(BaseModel):
    """Catalogo completo + los contratos (lectura, buffer, ack, mqtt)."""
    total_sensors: int
    biometric_sensors: list[str]
    devices: list[SensorCatalogDevice]
    contract: dict


# ── Registro de ingesta ──────────────────────────────────────────────────────

class IngestRecord(BaseModel):
    """
    Registro de una lectura GUARDADA en el servidor.

    - `timestamp`      : momento que el sensor dice que midio (fuente: ESP32)
    - `received_at`    : momento que el servidor la guardo (auditoria)
    - `sensor_id`      : de que sensor vino el dato
    - `buffer_id`      : a que envio (buffer) pertenecia
    """
    id: int
    device_id: str
    sensor_id: str
    value: float
    unit: str
    timestamp: datetime
    received_at: datetime
    buffer_id: Optional[str] = None
    sequence: Optional[int] = None


class IngestSummary(BaseModel):
    """Resumen de la ingesta: cuando se guardo y de que sensor vino."""
    total: int
    generated_at: datetime
    buffers: list[dict]
    records: list[IngestRecord]


# ── Modo de autenticacion ────────────────────────────────────────────────────

class AuthMode(BaseModel):
    """
    Modo de acceso del backend.

    `requires_login = False` significa que el dashboard publico puede entrar
    sin credenciales, usando `default_rol`. El filtrado por rol se mantiene
    intacto: el rol decide que datos se ven, no si se puede entrar.
    """
    requires_login: bool
    default_rol: str
    default_username: str

