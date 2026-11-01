"""
Tests del simulador del receptor LoRa (multi-sensor).

Cubre:
  - Las lecturas generadas siguen el contrato de datos de AGENTS.md.
  - Todos los sensor_id de DOMO_SENSORS aparecen en las lecturas.
  - Los valores de cada lectura estan dentro del rango de su sensor.
  - Cada sensor tiene su propio sequence incremental independiente.
  - El device_id es siempre el ESP32 del domo.
"""

import time
from collections import defaultdict

from gateway.domo_sensors import make_domo_sensors
from gateway.lora_receiver_sim import LoRaReceiverSim

REQUIRED_FIELDS = ("device_id", "sensor_id", "timestamp", "value", "unit", "sequence")
SENSOR_IDS = {s.sensor_id for s in make_domo_sensors()}
SENSOR_RANGES = {s.sensor_id: (s.value_min, s.value_max) for s in make_domo_sensors()}


class TestLoRaReceiverSim:

    def test_genera_lecturas_con_campos_del_contrato(self):
        """Todas las lecturas tienen los 6 campos del contrato de datos."""
        received = []
        sim = LoRaReceiverSim(on_reading=received.append, interval=0.05)
        sim.start()
        time.sleep(0.3)
        sim.stop()

        assert len(received) >= len(SENSOR_IDS), (
            f"Esperaba al menos {len(SENSOR_IDS)} lecturas, recibí {len(received)}"
        )
        for r in received:
            for campo in REQUIRED_FIELDS:
                assert campo in r, f"Campo '{campo}' ausente en {r['sensor_id']}"

    def test_todos_los_sensor_id_presentes(self):
        """Todos los sensores de DOMO_SENSORS generan al menos una lectura."""
        received = []
        sim = LoRaReceiverSim(on_reading=received.append, interval=0.05)
        sim.start()
        time.sleep(0.3)
        sim.stop()

        recibidos = {r["sensor_id"] for r in received}
        assert recibidos == SENSOR_IDS, (
            f"Sensores faltantes: {SENSOR_IDS - recibidos}"
        )

    def test_valores_dentro_del_rango_por_sensor(self):
        """Cada lectura tiene su valor dentro del rango de su sensor."""
        received = []
        sim = LoRaReceiverSim(on_reading=received.append, interval=0.05)
        sim.start()
        time.sleep(0.3)
        sim.stop()

        for r in received:
            lo, hi = SENSOR_RANGES[r["sensor_id"]]
            assert lo <= r["value"] <= hi, (
                f"{r['sensor_id']}: valor {r['value']} fuera de [{lo}, {hi}]"
            )

    def test_sequence_incremental_por_sensor(self):
        """Cada sensor tiene su propio sequence incremental [1, 2, ...]."""
        received = []
        sim = LoRaReceiverSim(on_reading=received.append, interval=0.05)
        sim.start()
        time.sleep(0.3)
        sim.stop()

        by_sensor: dict = defaultdict(list)
        for r in received:
            by_sensor[r["sensor_id"]].append(r["sequence"])

        for sid, seqs in by_sensor.items():
            expected = list(range(1, len(seqs) + 1))
            assert seqs == expected, (
                f"{sid}: sequences {seqs} != esperado {expected}"
            )

    def test_device_id_correcto(self):
        """Todas las lecturas tienen device_id == ESP32-01."""
        received = []
        sim = LoRaReceiverSim(on_reading=received.append, interval=0.05)
        sim.start()
        time.sleep(0.15)
        sim.stop()

        for r in received:
            assert r["device_id"] == "ESP32-01", (
                f"device_id incorrecto: {r['device_id']}"
            )

    def test_sensores_inyectados_custom(self):
        """Se pueden inyectar sensores custom para tests aislados."""
        from gateway.domo_sensors import SensorGenerator
        custom = [SensorGenerator("TEST-99", "C", 20.0, 25.0, 0.1)]
        received = []
        sim = LoRaReceiverSim(on_reading=received.append, interval=0.05, sensors=custom)
        sim.start()
        time.sleep(0.15)
        sim.stop()

        assert all(r["sensor_id"] == "TEST-99" for r in received)
        assert all(r["unit"] == "C" for r in received)
