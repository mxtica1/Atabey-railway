"""
Proceso principal del gateway — Mision Atabey.

Ata tres piezas:
  1. LoRaReceiverSim  — simula el tramo radio (ESP32 → Raspberry Pi)
  2. OfflineQueue      — cola SQLite persistente; toda lectura entra aqui primero
  3. GatewaySync       — hilo que drena la cola hacia el broker MQTT remoto

Flujo:
    LoRaReceiverSim
        └─ on_reading() -> queue.enqueue(reading)   [siempre, sin condicion]

    GatewaySync (hilo separado)
        └─ lee queue.pending()
           └─ publica al broker MQTT remoto
              └─ marca synced en SQLite

Ejecutar:
    python -m gateway.gateway

Variables de entorno (ver .env.example):
    MQTT_HOST   -- host del broker remoto (default: localhost)
    MQTT_PORT   -- puerto del broker remoto (default: 1883)
    QUEUE_DB    -- ruta a la base de datos SQLite (default: gateway_queue.db)
"""

import logging
import os
import signal
import time
from pathlib import Path

from dotenv import load_dotenv

from gateway.eva_receiver_sim import EvaReceiverSim
from gateway.lora_receiver_sim import LoRaReceiverSim
from gateway.queue import OfflineQueue
from gateway.sync import GatewaySync

load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    db_path = Path(os.getenv("QUEUE_DB", Path(__file__).parent / "gateway_queue.db"))

    queue = OfflineQueue(db_path=db_path)

    def on_reading(reading: dict) -> None:
        """
        Callback: toda lectura que llega por 'radio' se encola primero.
        Esta es la garantia offline-first de AGENTS.md.
        """
        queue.enqueue(reading)
        logger.info(
            "Encolado: [%s] %s = %s %s  seq=%d  pendientes=%d",
            reading.get("device_id", "UNKNOWN"),
            reading["sensor_id"],
            reading["value"],
            reading["unit"],
            reading["sequence"],
            queue.count_pending(),
        )

    receiver = LoRaReceiverSim(on_reading=on_reading)
    eva_receiver = EvaReceiverSim(on_reading=on_reading)
    syncer = GatewaySync(queue=queue)

    # Manejo de senales para apagado limpio
    stop_requested = False

    def _handle_signal(signum, frame):
        nonlocal stop_requested
        logger.info("Senal %d recibida, apagando gateway...", signum)
        stop_requested = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info("=== Gateway Atabey iniciado (Domo + Tripulante) ===")
    receiver.start()
    eva_receiver.start()
    syncer.start()

    try:
        while not stop_requested:
            time.sleep(1)
    finally:
        logger.info("Deteniendo componentes...")
        receiver.stop()
        eva_receiver.stop()
        syncer.stop()
        queue.close()
        logger.info("=== Gateway detenido ===")


if __name__ == "__main__":
    main()
