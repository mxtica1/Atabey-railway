"""
Tarea de sincronizacion del gateway — Mision Atabey.

Lee la cola SQLite e intenta publicar cada lectura pendiente al broker MQTT
remoto. Si la conexion no esta disponible, reintenta con backoff exponencial
(techo de 60s). Nunca descarta una lectura por numero de intentos fallidos.

Responsabilidades:
    - Es el UNICO modulo que habla con el broker MQTT remoto.
    - NO accede directamente a PostgreSQL; eso lo hace el backend al recibir
      el mensaje MQTT.
    - Se ejecuta en un hilo de fondo (daemon=True) para no bloquear la
      ingesta de lecturas entrantes.
"""

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional, Protocol

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from gateway.queue import OfflineQueue

load_dotenv(Path(__file__).parent / ".env")

logger = logging.getLogger(__name__)

MQTT_HOST: str = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT: int = int(os.getenv("MQTT_PORT", "1883"))
TOPIC_PREFIX: str = "atabey/domo/"

# Backoff exponencial
BACKOFF_BASE: float = 1.0   # segundos
BACKOFF_CEILING: float = 60.0
SYNC_IDLE_SLEEP: float = 2.0  # pausa entre ciclos cuando no hay pendientes


# ---------------------------------------------------------------------------
# Protocolo de cliente MQTT (facilita inyectar mocks en tests)
# ---------------------------------------------------------------------------

class MQTTClientProtocol(Protocol):
    """Interfaz minima que el sincronizador usa del cliente MQTT."""

    def connect(self, host: str, port: int, keepalive: int) -> int: ...
    def disconnect(self) -> None: ...
    def publish(self, topic: str, payload: str, qos: int) -> mqtt.MQTTMessageInfo: ...
    def loop_start(self) -> None: ...
    def loop_stop(self) -> None: ...
    def is_connected(self) -> bool: ...


# ---------------------------------------------------------------------------
# Sincronizador
# ---------------------------------------------------------------------------

class GatewaySync:
    """
    Sincronizador gateway → broker MQTT remoto.

    Uso tipico:
        syncer = GatewaySync(queue)
        syncer.start()          # arranca hilo de fondo
        ...
        syncer.stop()           # detiene con gracia
    """

    def __init__(
        self,
        queue: OfflineQueue,
        mqtt_client: Optional[MQTTClientProtocol] = None,
        mqtt_host: str = MQTT_HOST,
        mqtt_port: int = MQTT_PORT,
    ) -> None:
        self._queue = queue
        self._mqtt_host = mqtt_host
        self._mqtt_port = mqtt_port
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        if mqtt_client is not None:
            self._client: MQTTClientProtocol = mqtt_client
            self._external_client = True
        else:
            self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            self._external_client = False

        self._connected = False
        if not self._external_client:
            self._client.on_connect = self._on_connect      # type: ignore[assignment]
            self._client.on_disconnect = self._on_disconnect  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Callbacks MQTT (solo usados con cliente real)
    # ------------------------------------------------------------------

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if hasattr(reason_code, "is_failure"):
            ok = not reason_code.is_failure
        else:
            ok = reason_code == 0
        self._connected = ok
        if ok:
            logger.info(
                "Sync: conectado al broker %s:%d", self._mqtt_host, self._mqtt_port
            )
        else:
            logger.warning("Sync: conexion fallida: %s", reason_code)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        self._connected = False
        logger.warning("Sync: desconectado del broker (rc=%s)", reason_code)

    # ------------------------------------------------------------------
    # Hilo principal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        backoff = BACKOFF_BASE

        while not self._stop_event.is_set():
            # 1. Intentar conectar si no estamos conectados
            if not self._is_connected():
                connected = self._try_connect()
                if not connected:
                    logger.info("Sync: sin conexion, esperando %.1fs...", backoff)
                    self._stop_event.wait(timeout=backoff)
                    backoff = min(backoff * 2, BACKOFF_CEILING)
                    continue
                backoff = BACKOFF_BASE  # reset tras exito

            # 2. Drenar la cola
            drained_any = self._drain_queue()

            # 3. Pausa si no habia pendientes
            if not drained_any:
                self._stop_event.wait(timeout=SYNC_IDLE_SLEEP)

    def _is_connected(self) -> bool:
        """Comprueba si el cliente esta conectado."""
        if self._external_client:
            # Para mocks: esperamos que expongan is_connected()
            return self._client.is_connected()
        return self._connected

    def _try_connect(self) -> bool:
        """Intenta conectar al broker. Devuelve True si tiene exito."""
        if self._external_client:
            return self._client.is_connected()
        try:
            self._client.connect(self._mqtt_host, self._mqtt_port, keepalive=60)
            self._client.loop_start()
            # Esperar un momento para que on_connect dispare
            time.sleep(0.5)
            return self._connected
        except Exception as exc:
            logger.warning("Sync: no se pudo conectar al broker: %s", exc)
            return False

    def _drain_queue(self) -> bool:
        """
        Publica todas las lecturas pendientes. Devuelve True si publico alguna.
        Si falla una publicacion, aborta el ciclo (la lectura queda pendiente).
        """
        pending = self._queue.pending()
        if not pending:
            return False

        for item in pending:
            if self._stop_event.is_set():
                break

            row_id = item.pop("_row_id")
            topic = f"{TOPIC_PREFIX}{item['sensor_id']}"
            payload_str = json.dumps(item, default=str)

            try:
                result = self._client.publish(topic, payload_str, qos=1)
                # paho devuelve MQTTMessageInfo; mocks pueden devolver un objeto simple
                rc = getattr(result, "rc", result)
                if rc != mqtt.MQTT_ERR_SUCCESS:
                    logger.warning(
                        "Sync: publish fallido rc=%s para seq=%s. Abortando ciclo.",
                        rc,
                        item.get("sequence"),
                    )
                    self._connected = False
                    return True  # habia pendientes, aunque fallo

                self._queue.mark_synced(row_id)
                logger.info(
                    "Sync: publicado %s seq=%s -> %s",
                    item.get("sensor_id"),
                    item.get("sequence"),
                    topic,
                )
            except Exception as exc:
                logger.warning("Sync: error publicando seq=%s: %s", item.get("sequence"), exc)
                self._connected = False
                return True

        return True

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Arranca el hilo de sincronizacion en segundo plano."""
        self._thread = threading.Thread(
            target=self._run, name="gateway-sync", daemon=True
        )
        self._thread.start()
        logger.info("Hilo de sincronizacion iniciado.")

    def stop(self, timeout: float = 5.0) -> None:
        """Detiene el sincronizador con gracia."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        if not self._external_client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
        logger.info("Sincronizador detenido.")
