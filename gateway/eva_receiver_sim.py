"""
Simulador del receptor LoRa de la mochila EVA (Tripulante) -- Mision Atabey.

Representa el tramo radio "Mochila EVA -> ESP32 -> LoRa -> Gateway".
Genera lecturas periodicas de los 10 sensores de tripulante definidos en
`tripulante_sensors.py` y las entrega directamente al callback `on_reading`
del gateway para encolarse en la cola offline SQLite.

Cadencia: 5 segundos por sensor (igual que el domo).
"""

import logging
import threading
from typing import Callable, Optional

from gateway.tripulante_sensors import make_tripulante_sensors

logger = logging.getLogger(__name__)

INTERVAL_SECONDS: float = 5.0


class EvaReceiverSim:
    """
    Simula el receptor LoRa para la mochila del tripulante (EVA-01).

    En cada tick genera una lectura por sensor y la entrega al callback.
    Cada sensor mantiene su propio estado y contador de secuencia.
    """

    def __init__(
        self,
        on_reading: Callable[[dict], None],
        interval: float = INTERVAL_SECONDS,
        sensors: Optional[list] = None,
    ) -> None:
        self._on_reading = on_reading
        self._interval = interval
        self._sensors = (
            sensors if sensors is not None else make_tripulante_sensors()
        )
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _run(self) -> None:
        sensor_ids = [s.sensor_id for s in self._sensors]
        logger.info(
            "EvaReceiverSim iniciado -> %d sensores: %s  intervalo=%.1fs",
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
                    "LoRa EVA recibido: %s = %s %s (seq=%d)",
                    reading["sensor_id"],
                    reading["value"],
                    reading["unit"],
                    reading["sequence"],
                )

                try:
                    self._on_reading(reading)
                except Exception as exc:
                    logger.error(
                        "Error en callback on_reading EVA (%s): %s",
                        reading["sensor_id"],
                        exc,
                    )

            self._stop_event.wait(timeout=self._interval)

    def start(self) -> None:
        """Arranca el hilo simulador."""
        self._thread = threading.Thread(
            target=self._run, name="eva-receiver-sim", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        """Detiene el hilo con gracia."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        logger.info("EvaReceiverSim detenido.")
