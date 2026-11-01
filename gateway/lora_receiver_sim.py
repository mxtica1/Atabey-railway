"""
Simulador del receptor LoRa del gateway -- Mision Atabey.

Representa el tramo "Sensor -> ESP32 -> LoRa -> Gateway" que en la mision real
ocurre por radio corta entre el domo y la Raspberry Pi. Este hop es siempre
local y nunca depende de Internet.

En cada tick (cada `interval` segundos) genera UNA lectura por cada sensor
definido en `domo_sensors.DOMO_SENSORS` y la entrega al callback proporcionado
DIRECTAMENTE -- sin publicar por MQTT ni pasar por Mosquitto.

Uso:
    from gateway.lora_receiver_sim import LoRaReceiverSim

    def on_reading(reading: dict) -> None:
        queue.enqueue(reading)

    sim = LoRaReceiverSim(on_reading=on_reading)
    sim.start()
    ...
    sim.stop()
"""

import logging
import threading
from typing import Callable, Optional

from gateway.domo_sensors import SensorGenerator, make_domo_sensors

logger = logging.getLogger(__name__)

INTERVAL_SECONDS: float = 5.0


class LoRaReceiverSim:
    """
    Simula el receptor LoRa del gateway orquestando todos los sensores del domo.

    En cada tick genera una lectura por sensor y la entrega al callback.
    Cada sensor tiene su propio estado (valor actual + sequence) independiente.

    El hilo es daemon=True para que no bloquee el apagado del proceso.
    """

    def __init__(
        self,
        on_reading: Callable[[dict], None],
        interval: float = INTERVAL_SECONDS,
        sensors: Optional[list] = None,
    ) -> None:
        self._on_reading = on_reading
        self._interval = interval
        # Crear instancias frescas si no se inyectan desde fuera
        self._sensors: list[SensorGenerator] = (
            sensors if sensors is not None else make_domo_sensors()
        )
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _run(self) -> None:
        sensor_ids = [s.sensor_id for s in self._sensors]
        logger.info(
            "LoRaReceiverSim iniciado -> %d sensores: %s  intervalo=%.1fs",
            len(self._sensors),
            ", ".join(sensor_ids),
            self._interval,
        )

        while not self._stop_event.is_set():
            for sensor in self._sensors:
                if self._stop_event.is_set():
                    break

                reading = sensor.next_reading()
                logger.debug(
                    "LoRa recibido: %s = %.2f %s (seq=%d)",
                    reading["sensor_id"],
                    reading["value"],
                    reading["unit"],
                    reading["sequence"],
                )

                try:
                    self._on_reading(reading)
                except Exception as exc:
                    logger.error(
                        "Error en callback on_reading (%s): %s",
                        reading["sensor_id"],
                        exc,
                    )

            self._stop_event.wait(timeout=self._interval)

    def start(self) -> None:
        """Arranca el hilo simulador."""
        self._thread = threading.Thread(
            target=self._run, name="lora-receiver-sim", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        """Detiene el hilo con gracia."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        logger.info("LoRaReceiverSim detenido.")
