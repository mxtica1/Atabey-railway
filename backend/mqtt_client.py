"""
Cliente MQTT para el backend de Mision Atabey.

Se suscribe a `atabey/domo/TEMP-01`, valida cada mensaje con Pydantic y lo
persiste en PostgreSQL. Los mensajes invalidos se descartan con un log de
advertencia; nunca se propaga una excepcion que pueda tumbar el backend.

Ademas de lecturas individuales, soporta BUFFERS DE DATOS:
  - Topico de entrada : atabey/{device_id}/buffer  (o atabey/buffer)
  - Topico de ACK     : atabey/ack/{device_id}
Un buffer es un lote de lecturas; al procesarlo el servidor guarda todo y
devuelve un ACK item por item para que el emisor sepa que llego y de que
sensor. Ver `docs/BUFFER_PROTOCOL.md`.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from pydantic import ValidationError

import backend.db as db
from backend.models import BatchAck, BatchItemAck, LocationUpdate, ReadingBatch, SensorReading
from backend.ws_manager import manager

load_dotenv(Path(__file__).parent / ".env")

logger = logging.getLogger(__name__)

MQTT_HOST: str = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT: int = int(os.getenv("MQTT_PORT", "1883"))
TOPIC: str = os.getenv("MQTT_TOPIC", "atabey/#")

# Patron de topico para actualizaciones de posicion GPS del tripulante
# atabey/eva/{device_id}/location
LOCATION_TOPIC_SUFFIX = "/location"

# Sufijo del topico de buffer de datos y prefijo del topico de ACK
BUFFER_TOPIC_SUFFIX = "/buffer"
ACK_TOPIC_PREFIX = "atabey/ack/"

_client: Optional[mqtt.Client] = None


# -- Callbacks ---------------------------------------------------------------

def on_connect(client, userdata, connect_flags, reason_code, properties):
    if reason_code.is_failure:
        logger.error("MQTT fallo al conectar: %s", reason_code)
    else:
        logger.info("MQTT conectado al broker %s:%d", MQTT_HOST, MQTT_PORT)
        client.subscribe(TOPIC)
        logger.info("Suscrito a %s", TOPIC)


def on_message(client, userdata, msg):
    """
    Callback invocado por paho-mqtt al recibir un mensaje.

    Ramifica por topico:
    - atabey/ack/**              → publicados por nosotros, se ignoran
    - Topicos que terminan en /location → pipeline de posicion GPS (LocationUpdate)
    - Topicos que terminan en /buffer   → pipeline de buffer de datos (ReadingBatch + ACK)
    - Resto → pipeline de telemetria de sensores (SensorReading + umbral + alerta)
    Nunca propaga excepciones.
    """
    topic = str(getattr(msg, "topic", "") or "")

    # Evitar eco: el ACK que publicamos vuelve a la suscripcion.
    if topic.startswith(ACK_TOPIC_PREFIX):
        return

    if topic.endswith(LOCATION_TOPIC_SUFFIX):
        _handle_location(msg)
    elif topic.endswith(BUFFER_TOPIC_SUFFIX) or topic == "atabey/buffer":
        _handle_buffer(msg, topic)
    else:
        _handle_reading(msg)


def _handle_location(msg) -> None:
    """Procesa un mensaje de posicion GPS."""
    try:
        payload  = json.loads(msg.payload.decode("utf-8"))
        location = LocationUpdate(**payload)
        db.insert_location(location)

        logger.info(
            "Posicion guardada: [%s] (%.6f, %.6f) seq=%d",
            location.device_id, location.lat, location.lon, location.sequence,
        )

        manager.broadcast_sync({
            "type":      "location",
            "device_id": location.device_id,
            "lat":       location.lat,
            "lon":       location.lon,
            "timestamp": location.timestamp.isoformat(),
            "sequence":  location.sequence,
            "sexo":      getattr(location, "sexo", None),
        })

    except json.JSONDecodeError as exc:
        logger.warning("Posicion: payload JSON invalido descartado: %s", exc)
    except ValidationError as exc:
        logger.warning("Posicion: mensaje no cumple el esquema, descartado: %s", exc)
    except Exception as exc:
        logger.error("Error inesperado procesando posicion: %s", exc)


def _handle_buffer(msg, topic: str = "") -> None:
    """
    Procesa un BUFFER DE DATOS: guarda todas las lecturas y publica el ACK.

    El ACK se publica en `atabey/ack/{device_id}` para que el ESP32/firmware
    sepa que el buffer llego, y se reenvia tambien por WebSocket al dashboard.
    """
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        batch = ReadingBatch(**payload)

        ack = ingest_batch(batch)

        logger.info(
            "Buffer %s de [%s]: %d aceptadas, %d duplicadas, %d rechazadas",
            batch.buffer_id, batch.device_id, ack.accepted, ack.duplicates, ack.rejected,
        )

        publish_ack(ack)

    except json.JSONDecodeError as exc:
        logger.warning("Buffer: payload JSON invalido descartado: %s", exc)
    except ValidationError as exc:
        logger.warning("Buffer: mensaje no cumple el esquema, descartado: %s", exc)
    except Exception as exc:
        logger.error("Error inesperado procesando buffer MQTT: %s", exc)


def ingest_batch(batch: ReadingBatch) -> BatchAck:
    """
    Guarda un buffer completo y construye el ACK.

    Idempotencia: si el `buffer_id` ya fue guardado, no se duplica nada y se
    devuelve el ACK con las lecturas previamente almacenadas.
    """
    received_at = datetime.now(timezone.utc)

    # Idempotencia — el mismo buffer reenviado no se procesa dos veces.
    existing = db.get_buffer_readings(batch.buffer_id)
    if existing:
        logger.info("Buffer %s ya recibido; devolviendo ACK original.", batch.buffer_id)
        items = [
            BatchItemAck(
                sensor_id=row["sensor_id"],
                sequence=row["sequence"],
                status="duplicate",
                received_at=row["received_at"],
                db_id=row["id"],
            )
            for row in existing
        ]
        return BatchAck(
            device_id=batch.device_id,
            buffer_id=batch.buffer_id,
            received_at=received_at,
            accepted=0,
            rejected=0,
            duplicates=len(items),
            items=items,
        )

    # Guardado en una transaccion: o entra todo el buffer, o nada.
    rows = db.insert_reading_batch(batch.readings, buffer_id=batch.buffer_id)

    items: list[BatchItemAck] = []
    for reading, row in zip(batch.readings, rows):
        items.append(BatchItemAck(
            sensor_id=reading.sensor_id,
            sequence=reading.sequence,
            status="stored",
            received_at=row["received_at"],
            db_id=row["id"],
        ))

    # Cada lectura del buffer pasa por el mismo ciclo de umbral/alerta que
    # una lectura individual.
    for reading in batch.readings:
        try:
            _evaluate_thresholds(reading)
        except Exception as exc:  # noqa: BLE001 - una alerta fallida no debe tumbar el buffer
            logger.error("Error evaluando umbral de %s: %s", reading.sensor_id, exc)

    # Aviso al dashboard por WebSocket.
    for reading in batch.readings:
        manager.broadcast_sync({
            "type": "reading",
            "device_id": reading.device_id,
            "sensor_id": reading.sensor_id,
            "value": reading.value,
            "unit": reading.unit,
            "timestamp": reading.timestamp.isoformat(),
            "sequence": reading.sequence,
            "buffer_id": batch.buffer_id,
        })

    manager.broadcast_sync({
        "type": "ingest",
        "device_id": batch.device_id,
        "buffer_id": batch.buffer_id,
        "received_at": received_at.isoformat(),
        "accepted": len(items),
        "items": [item.model_dump(mode="json") for item in items],
    })

    ack = BatchAck(
        device_id=batch.device_id,
        buffer_id=batch.buffer_id,
        received_at=received_at,
        accepted=len(items),
        rejected=0,
        duplicates=0,
        items=items,
    )
    
    # Registrar ACK en auditoría
    db.insert_ingest_ack(
        device_id=batch.device_id,
        buffer_id=batch.buffer_id,
        total_items=len(batch.readings),
        accepted=len(items),
        rejected=0,
        duplicates=0,
    )
    
    return ack


def publish_ack(ack: BatchAck) -> None:
    """Publica el ACK en `atabey/ack/{device_id}` para que el emisor lo reciba."""
    if _client is None:
        logger.warning("No hay cliente MQTT; ACK de %s no publicado.", ack.buffer_id)
        return
    topic = f"{ACK_TOPIC_PREFIX}{ack.device_id}"
    payload = json.dumps(ack.model_dump(mode="json"))
    result = _client.publish(topic, payload, qos=1)
    status = "OK" if result.rc == mqtt.MQTT_ERR_SUCCESS else f"ERR rc={result.rc}"
    logger.info("ACK publicado en %s (%s): %s", topic, status, ack.buffer_id)


def _handle_reading(msg) -> None:
    """Procesa un mensaje de lectura de sensor (logica original)."""
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        reading = SensorReading(**payload)
        db.insert_reading(reading)

        logger.info(
            "Lectura guardada: [%s] %s = %s %s (seq=%d)",
            reading.device_id,
            reading.sensor_id,
            reading.value,
            reading.unit,
            reading.sequence,
        )

        # Broadcast de la lectura normal
        manager.broadcast_sync({
            "type": "reading",
            "device_id": reading.device_id,
            "sensor_id": reading.sensor_id,
            "value": reading.value,
            "unit": reading.unit,
            "timestamp": reading.timestamp.isoformat(),
            "sequence": reading.sequence,
        })

        # Verificacion de umbral + ciclo de vida de alerta
        _evaluate_thresholds(reading)

    except json.JSONDecodeError as exc:
        logger.warning("Payload JSON invalido descartado: %s", exc)
    except ValidationError as exc:
        logger.warning("Mensaje no cumple el esquema, descartado: %s", exc)
    except Exception as exc:
        logger.error("Error inesperado procesando mensaje MQTT: %s", exc)


def _evaluate_thresholds(reading: SensorReading) -> None:
    """
    Verifica el umbral de la lectura y gestiona el ciclo de vida de la alerta.

    Compartido por el pipeline de lectura individual y el de buffer, para que
    ambos usen EXACTAMENTE el mismo criterio de severidad.
    """
    threshold = db.get_threshold(reading.sensor_id)
    if threshold is None:
        return

    excedido = None
    if reading.value < threshold["valor_min"]:
        excedido = "min"
    elif reading.value > threshold["valor_max"]:
        excedido = "max"

    if excedido is not None:
        # Severidad: "critico" si supera el umbral en mas del 20%, "advertencia" si no
        rango = threshold["valor_max"] - threshold["valor_min"]
        margen = abs(
            reading.value - threshold["valor_min"]
            if excedido == "min"
            else reading.value - threshold["valor_max"]
        )
        severidad = "critico" if rango > 0 and margen / rango > 0.20 else "advertencia"

        # Deduplicacion: buscar alerta activa existente para este sensor+direccion
        existing = db.get_active_alert(reading.sensor_id, excedido)
        if existing is not None:
            # Actualizar value y visto_por_ultima_vez en la alerta existente
            alert = db.update_alert_value(existing["id"], reading.value, reading.timestamp)
        else:
            # Crear alerta nueva solo si no habia una activa
            alert = db.insert_alert(
                sensor_id=reading.sensor_id,
                value=reading.value,
                threshold_excedido=excedido,
                valor_min=threshold["valor_min"],
                valor_max=threshold["valor_max"],
                timestamp=reading.timestamp,
                severidad=severidad,
            )

        manager.broadcast_sync({
            "type": "alert",
            "id": alert["id"],
            "sensor_id": reading.sensor_id,
            "value": reading.value,
            "threshold_excedido": excedido,
            "valor_min": threshold["valor_min"],
            "valor_max": threshold["valor_max"],
            "timestamp": reading.timestamp.isoformat(),
            "severidad": alert["severidad"],
        })

    else:
        # Lectura dentro de rango — resolver alertas activas en cualquier direccion
        for direccion in ("min", "max"):
            active = db.get_active_alert(reading.sensor_id, direccion)
            if active is not None:
                db.resolve_alert(active["id"], resuelto_por=None)
                logger.info(
                    "Alerta %d auto-resuelta: %s volvio a rango.",
                    active["id"], reading.sensor_id,
                )


# -- Lifecycle ---------------------------------------------------------------

def start() -> None:
    """Conecta al broker y arranca el loop MQTT en un hilo de fondo."""
    global _client
    _client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    _client.on_connect = on_connect
    _client.on_message = on_message

    for attempt in range(10):
        try:
            _client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            break
        except Exception as exc:
            wait = 3
            logger.warning(
                "MQTT: intento %d/10 fallido (%s). Reintentando en %ds...",
                attempt + 1,
                exc,
                wait,
            )
            time.sleep(wait)
    else:
        raise RuntimeError(
            f"No se pudo conectar al broker MQTT en {MQTT_HOST}:{MQTT_PORT} "
            "despues de 10 intentos."
        )

    _client.loop_start()
    logger.info("MQTT loop iniciado.")


def stop() -> None:
    """Detiene el loop MQTT y desconecta."""
    global _client
    if _client is not None:
        _client.loop_stop()
        _client.disconnect()
        _client = None
        logger.info("MQTT desconectado.")
