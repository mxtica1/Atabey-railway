"""
Tests del Modulo 3: generadores de sensores del domo.

Cubre los tres criterios del prompt:
  1. Cada generador produce valores dentro de su rango y con la unidad correcta.
  2. Cada sensor mantiene su propio sequence incremental, independiente de los
     demas sensores.
  3. Con varios sensor_id intercalados en la cola, el drenado no pierde,
     duplica ni cruza lecturas entre sensores.
"""

import json
from collections import defaultdict
from unittest.mock import MagicMock

import pytest

from gateway.domo_sensors import DOMO_SENSORS, SensorGenerator, make_domo_sensors, DEVICE_ID
from gateway.lora_receiver_sim import LoRaReceiverSim
from gateway.queue import OfflineQueue
from gateway.sync import GatewaySync

REQUIRED_FIELDS = ("device_id", "sensor_id", "timestamp", "value", "unit", "sequence")


# ---------------------------------------------------------------------------
# 1. Rango y unidad por sensor
# ---------------------------------------------------------------------------

class TestSensorGenerator:

    @pytest.mark.parametrize("sensor", make_domo_sensors(), ids=lambda s: s.sensor_id)
    def test_valores_dentro_del_rango(self, sensor: SensorGenerator):
        """50 lecturas consecutivas caen dentro de [value_min, value_max]."""
        for _ in range(50):
            r = sensor.next_reading()
            assert sensor.value_min <= r["value"] <= sensor.value_max, (
                f"{sensor.sensor_id}: valor {r['value']} fuera de "
                f"[{sensor.value_min}, {sensor.value_max}]"
            )

    @pytest.mark.parametrize("sensor", make_domo_sensors(), ids=lambda s: s.sensor_id)
    def test_unidad_correcta(self, sensor: SensorGenerator):
        """La unidad en la lectura coincide con la definida en el generador."""
        r = sensor.next_reading()
        assert r["unit"] == sensor.unit, (
            f"{sensor.sensor_id}: unidad {r['unit']!r} != esperada {sensor.unit!r}"
        )

    @pytest.mark.parametrize("sensor", make_domo_sensors(), ids=lambda s: s.sensor_id)
    def test_campos_del_contrato(self, sensor: SensorGenerator):
        """Todos los campos del contrato de datos estan presentes."""
        r = sensor.next_reading()
        for campo in REQUIRED_FIELDS:
            assert campo in r, f"{sensor.sensor_id}: campo '{campo}' ausente"
        assert r["device_id"] == DEVICE_ID
        assert r["sensor_id"] == sensor.sensor_id

    def test_todos_los_sensor_id_unicos(self):
        """Cada sensor_id en DOMO_SENSORS es unico."""
        ids = [s.sensor_id for s in make_domo_sensors()]
        assert len(ids) == len(set(ids)), f"sensor_ids duplicados: {ids}"

    def test_hay_13_sensores(self):
        """DOMO_SENSORS contiene los 13 sensores del domo."""
        sensors = make_domo_sensors()
        assert len(sensors) == 13, f"Se esperaban 13 sensores, hay {len(sensors)}"

    def test_sensor_ids_esperados(self):
        """Los sensor_id coinciden con los definidos en el Modulo 3."""
        esperados = {
            "TEMP-01", "HUM-01", "CO2-01", "LUX-01",
            "SOIL-HUM-01", "SOIL-HUM-02", "SOIL-HUM-03",
            "SOIL-TEMP-01", "SOIL-TEMP-02", "SOIL-TEMP-03",
            "NPK-N-01", "NPK-P-01", "NPK-K-01",
        }
        obtenidos = {s.sensor_id for s in make_domo_sensors()}
        assert obtenidos == esperados, (
            f"Diferencia: falta={esperados - obtenidos}, extra={obtenidos - esperados}"
        )


# ---------------------------------------------------------------------------
# 2. Sequence independiente por sensor
# ---------------------------------------------------------------------------

class TestSensorSequencesIndependientes:

    def test_sequences_empiezan_en_1(self):
        """Cada generador fresco empieza con sequence=1."""
        for sensor in make_domo_sensors():
            r = sensor.next_reading()
            assert r["sequence"] == 1, (
                f"{sensor.sensor_id}: sequence inicial deberia ser 1, es {r['sequence']}"
            )

    def test_avanzar_a_no_afecta_a_b(self):
        """El sequence de un sensor no afecta al de otro."""
        gen_a = SensorGenerator("A-01", "C", 0.0, 100.0, 1.0)
        gen_b = SensorGenerator("B-01", "%", 0.0, 100.0, 1.0)

        for _ in range(7):
            gen_a.next_reading()

        r_b = gen_b.next_reading()
        assert r_b["sequence"] == 1, (
            f"Sequence de B deberia ser 1 tras avanzar A 7 veces, es {r_b['sequence']}"
        )

    def test_sequence_incremental_por_sensor(self):
        """El sequence de cada sensor es estrictamente [1, 2, ..., N]."""
        gen = SensorGenerator("X-01", "ppm", 400.0, 1200.0, 10.0)
        seqs = [gen.next_reading()["sequence"] for _ in range(10)]
        assert seqs == list(range(1, 11)), f"Sequences no incrementales: {seqs}"

    def test_todos_los_sensores_sequences_independientes(self):
        """
        Simula N ticks del orquestador: cada sensor_id tiene sequences [1..N]
        independientes de los demas.
        """
        N_TICKS = 5
        sensors = make_domo_sensors()

        by_sensor: dict = defaultdict(list)
        for _ in range(N_TICKS):
            for sensor in sensors:
                r = sensor.next_reading()
                by_sensor[r["sensor_id"]].append(r["sequence"])

        for sensor_id, seqs in by_sensor.items():
            expected = list(range(1, N_TICKS + 1))
            assert seqs == expected, (
                f"Sensor {sensor_id}: sequences {seqs} != esperado {expected}"
            )

    def test_make_domo_sensors_devuelve_instancias_frescas(self):
        """
        Dos llamadas a make_domo_sensors() devuelven objetos distintos,
        con sequences independientes entre si.
        """
        batch_a = make_domo_sensors()
        batch_b = make_domo_sensors()

        for sa in batch_a:
            sa.next_reading()  # avanza sequence de A

        for sa, sb in zip(batch_a, batch_b):
            assert sa is not sb, "make_domo_sensors devolvio la misma instancia"
            rb = sb.next_reading()
            assert rb["sequence"] == 1, (
                f"{sb.sensor_id}: sequence de batch_b deberia ser 1, es {rb['sequence']}"
            )


# ---------------------------------------------------------------------------
# 3. Sin perdida ni cruce en la cola con multiples sensores
# ---------------------------------------------------------------------------

class TestQueueMultiSensor:

    def test_cola_total_lecturas_correcta(self, tmp_queue: OfflineQueue):
        """count_total() == N_TICKS * N_SENSORS tras encolar intercalado."""
        N_TICKS = 10
        sensors = make_domo_sensors()

        for _ in range(N_TICKS):
            for sensor in sensors:
                tmp_queue.enqueue(sensor.next_reading())

        total = tmp_queue.count_total()
        esperado = N_TICKS * len(sensors)
        assert total == esperado, f"Total esperado {esperado}, obtenido {total}"

    def test_no_hay_duplicados_en_cola(self, tmp_queue: OfflineQueue):
        """No hay pares (sensor_id, sequence) repetidos."""
        N_TICKS = 5
        sensors = make_domo_sensors()

        for _ in range(N_TICKS):
            for sensor in sensors:
                tmp_queue.enqueue(sensor.next_reading())

        # INSERT OR IGNORE: re-encolar el mismo reading no crea duplicados
        sensors2 = make_domo_sensors()
        for _ in range(N_TICKS):
            for sensor in sensors2:
                tmp_queue.enqueue(sensor.next_reading())

        # Solo deben existir N_TICKS * N_SENSORS filas (no el doble)
        total = tmp_queue.count_total()
        esperado = N_TICKS * len(sensors)
        assert total == esperado, (
            f"INSERT OR IGNORE fallo: esperado {esperado}, obtenido {total}"
        )

    def test_drenado_sin_perdida_ni_cruce(self, tmp_queue: OfflineQueue):
        """
        Drena la cola con un mock MQTT y verifica:
        - Publicadas == encoladas (sin perdidas)
        - Cada (sensor_id, sequence) aparece exactamente una vez (sin duplicados)
        - Los payloads tienen campos coherentes (sin cruce entre sensores)
        """
        N_TICKS = 5
        sensors = make_domo_sensors()

        for _ in range(N_TICKS):
            for sensor in sensors:
                tmp_queue.enqueue(sensor.next_reading())

        published: list = []

        mock_result = MagicMock()
        mock_result.rc = 0  # MQTT_ERR_SUCCESS

        mock_client = MagicMock()
        mock_client.is_connected.return_value = True
        mock_client.publish.return_value = mock_result

        def capture_publish(topic, payload, qos):
            published.append(json.loads(payload))
            return mock_result

        mock_client.publish.side_effect = capture_publish

        syncer = GatewaySync(queue=tmp_queue, mqtt_client=mock_client)
        # Drenar en lotes hasta vaciar
        while tmp_queue.count_pending() > 0:
            syncer._drain_queue()

        esperado = N_TICKS * len(sensors)
        assert len(published) == esperado, (
            f"Publicadas: {len(published)}, esperadas: {esperado}"
        )

        # Sin duplicados
        pairs = [(r["sensor_id"], r["sequence"]) for r in published]
        assert len(pairs) == len(set(pairs)), "Hay pares (sensor_id, sequence) duplicados"

        # Sin cruce: el payload de cada lectura tiene coherencia interna
        sensor_units = {s.sensor_id: s.unit for s in make_domo_sensors()}
        for r in published:
            assert r["device_id"] == DEVICE_ID
            assert r["sensor_id"] in sensor_units
            assert r["unit"] == sensor_units[r["sensor_id"]], (
                f"{r['sensor_id']}: unidad {r['unit']} no coincide con la esperada "
                f"{sensor_units[r['sensor_id']]}"
            )

    def test_pending_se_vacia_tras_drenado(self, tmp_queue: OfflineQueue):
        """Despues del drenado completo, count_pending() == 0."""
        sensors = make_domo_sensors()
        for sensor in sensors:
            tmp_queue.enqueue(sensor.next_reading())

        mock_result = MagicMock()
        mock_result.rc = 0
        mock_client = MagicMock()
        mock_client.is_connected.return_value = True
        mock_client.publish.return_value = mock_result

        syncer = GatewaySync(queue=tmp_queue, mqtt_client=mock_client)
        while tmp_queue.count_pending() > 0:
            syncer._drain_queue()

        assert tmp_queue.count_pending() == 0
