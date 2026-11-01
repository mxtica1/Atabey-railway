"""
Tests del orquestador EvaReceiverSim.
"""

import time
from collections import defaultdict

from gateway.eva_receiver_sim import EvaReceiverSim
from gateway.tripulante_sensors import make_tripulante_sensors

REQUIRED_FIELDS = ("device_id", "sensor_id", "timestamp", "value", "unit", "sequence")
SENSOR_IDS = {s.sensor_id for s in make_tripulante_sensors()}


class TestEvaReceiverSim:

    def test_genera_lecturas_con_campos_del_contrato(self):
        received = []
        sim = EvaReceiverSim(on_reading=received.append, interval=0.05)
        sim.start()
        time.sleep(0.3)
        sim.stop()

        assert len(received) >= len(SENSOR_IDS)
        for r in received:
            for campo in REQUIRED_FIELDS:
                assert campo in r, f"Campo '{campo}' ausente en {r['sensor_id']}"
            assert r["device_id"] == "EVA-01"

    def test_todos_los_sensores_presentes(self):
        received = []
        sim = EvaReceiverSim(on_reading=received.append, interval=0.05)
        sim.start()
        time.sleep(0.3)
        sim.stop()

        recibidos = {r["sensor_id"] for r in received}
        assert recibidos == SENSOR_IDS

    def test_sequence_incremental_por_sensor(self):
        received = []
        sim = EvaReceiverSim(on_reading=received.append, interval=0.05)
        sim.start()
        time.sleep(0.3)
        sim.stop()

        by_sensor = defaultdict(list)
        for r in received:
            by_sensor[r["sensor_id"]].append(r["sequence"])

        for sid, seqs in by_sensor.items():
            expected = list(range(1, len(seqs) + 1))
            assert seqs == expected
