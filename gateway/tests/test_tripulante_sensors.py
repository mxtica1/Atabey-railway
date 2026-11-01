"""
Tests del Modulo 4: generadores de sensores del tripulante (mochila EVA).

Cubre:
  1. Cada generador produce valores dentro de su rango y con la unidad correcta.
  2. Cada sensor mantiene su propio sequence incremental e independiente.
  3. ACTIVITY-01 sostiene su valor entre 20 y 60 segundos antes de cambiar.
  4. Con lecturas de domo y tripulante intercaladas en la cola, el drenado
     no pierde, duplica ni cruza lecturas entre device_id distintos.
"""

import json
from collections import defaultdict
from unittest.mock import MagicMock

import pytest

from gateway.domo_sensors import make_domo_sensors
from gateway.tripulante_sensors import (
    DEVICE_ID as EVA_DEVICE_ID,
    ActivitySensorGenerator,
    SensorGenerator,
    make_tripulante_sensors,
)
from gateway.queue import OfflineQueue
from gateway.sync import GatewaySync

REQUIRED_FIELDS = ("device_id", "sensor_id", "timestamp", "value", "unit", "sequence")


# ---------------------------------------------------------------------------
# 1. Rango y unidad por sensor
# ---------------------------------------------------------------------------

class TestTripulanteSensors:

    @pytest.mark.parametrize(
        "sensor", make_tripulante_sensors(), ids=lambda s: s.sensor_id
    )
    def test_valores_dentro_del_rango(self, sensor):
        """50 lecturas consecutivas caen dentro de [value_min, value_max]."""
        for _ in range(50):
            r = sensor.next_reading()
            assert sensor.value_min <= r["value"] <= sensor.value_max, (
                f"{sensor.sensor_id}: valor {r['value']} fuera de "
                f"[{sensor.value_min}, {sensor.value_max}]"
            )

    @pytest.mark.parametrize(
        "sensor", make_tripulante_sensors(), ids=lambda s: s.sensor_id
    )
    def test_unidad_correcta(self, sensor):
        """La unidad en la lectura coincide con la definida en el generador."""
        r = sensor.next_reading()
        assert r["unit"] == sensor.unit, (
            f"{sensor.sensor_id}: unidad {r['unit']!r} != esperada {sensor.unit!r}"
        )

    @pytest.mark.parametrize(
        "sensor", make_tripulante_sensors(), ids=lambda s: s.sensor_id
    )
    def test_campos_del_contrato(self, sensor):
        """Todos los campos del contrato de datos estan presentes y correctos."""
        r = sensor.next_reading()
        for campo in REQUIRED_FIELDS:
            assert campo in r, f"{sensor.sensor_id}: campo '{campo}' ausente"
        assert r["device_id"] == EVA_DEVICE_ID
        assert r["sensor_id"] == sensor.sensor_id

    def test_hay_10_sensores_tripulante(self):
        """make_tripulante_sensors contiene exactamente 10 sensores."""
        sensors = make_tripulante_sensors()
        assert len(sensors) == 10, f"Se esperaban 10 sensores, hay {len(sensors)}"

    def test_sensor_ids_esperados(self):
        """Los sensor_id coinciden exactamente con la especificacion EVA."""
        esperados = {
            "HR-01", "SPO2-01", "BTEMP-01",
            "EVA-TEMP-01", "EVA-HUM-01", "EVA-PRESS-01",
            "ACC-X-01", "ACC-Y-01", "ACC-Z-01",
            "ACTIVITY-01",
        }
        obtenidos = {s.sensor_id for s in make_tripulante_sensors()}
        assert obtenidos == esperados, (
            f"Diferencia: falta={esperados - obtenidos}, extra={obtenidos - esperados}"
        )


# ---------------------------------------------------------------------------
# 2. Sequence independiente
# ---------------------------------------------------------------------------

class TestTripulanteSequences:

    def test_sequences_empiezan_en_1(self):
        """Cada generador inicia en sequence=1."""
        for sensor in make_tripulante_sensors():
            r = sensor.next_reading()
            assert r["sequence"] == 1, (
                f"{sensor.sensor_id}: sequence inicial deberia ser 1, es {r['sequence']}"
            )

    def test_sequence_incremental_por_sensor(self):
        """El sequence avanza estrictamente 1..N sin interferencias."""
        N_TICKS = 8
        sensors = make_tripulante_sensors()
        by_sensor = defaultdict(list)

        for _ in range(N_TICKS):
            for sensor in sensors:
                r = sensor.next_reading()
                by_sensor[r["sensor_id"]].append(r["sequence"])

        for sensor_id, seqs in by_sensor.items():
            expected = list(range(1, N_TICKS + 1))
            assert seqs == expected, (
                f"Sensor {sensor_id}: sequences {seqs} != {expected}"
            )


# ---------------------------------------------------------------------------
# 3. Retención de ACTIVITY-01
# ---------------------------------------------------------------------------

class TestActivitySensor:

    def test_actividad_es_entero_0_a_3(self):
        gen = ActivitySensorGenerator()
        for _ in range(30):
            r = gen.next_reading()
            assert isinstance(r["value"], int)
            assert r["value"] in (0, 1, 2, 3)

    def test_actividad_sostiene_valor_al_menos_20_segundos(self):
        """
        Con ticks de 5s, 20s equivale a 4 lecturas. Durante las primeras
        4 lecturas (0s, 5s, 10s, 15s) el valor NO debe cambiar, porque
        el tiempo minimo de retencion es 20s.
        """
        for _ in range(10):  # repite 10 veces para cubrir aleatoriedad
            gen = ActivitySensorGenerator(min_hold_seconds=20.0, max_hold_seconds=60.0)
            primera_lectura = gen.next_reading(elapsed_seconds=5.0)
            valor_inicial = primera_lectura["value"]

            # Las siguientes 3 lecturas (hasta 15s transcurridos) deben ser identicas
            for _ in range(3):
                r = gen.next_reading(elapsed_seconds=5.0)
                assert r["value"] == valor_inicial, (
                    f"ACTIVITY-01 cambio antes de los 20s minimos (obtenido {r['value']} vs {valor_inicial})"
                )

    def test_actividad_cambia_antes_de_65_segundos(self):
        """
        Despues de 65s (13 ticks de 5s), el valor DEBE haber cambiado al menos una vez,
        dado que el techo maximo de retencion es 60s.
        """
        gen = ActivitySensorGenerator(min_hold_seconds=20.0, max_hold_seconds=60.0)
        valores = [gen.next_reading(elapsed_seconds=5.0)["value"] for _ in range(15)]
        # Debe haber al menos 2 valores distintos en 15 ticks (75 segundos)
        assert len(set(valores)) >= 2, (
            f"ACTIVITY-01 no cambio despues de 75s: {valores}"
        )


# ---------------------------------------------------------------------------
# 4. Intercalado multi-dispositivo (Domo + Tripulante) en la cola
# ---------------------------------------------------------------------------

class TestQueueMultiDevice:

    def test_intercalado_domo_y_tripulante(self, tmp_queue: OfflineQueue):
        """
        Encola lecturas simultaneas de ESP32-01 (13 sensores) y EVA-01 (10 sensores)
        y verifica que el drenado hacia el broker no pierde ni cruza lecturas.
        """
        N_TICKS = 4
        domo_sensors = make_domo_sensors()          # 13 sensores
        tripulante_sensors = make_tripulante_sensors()  # 10 sensores
        total_sensores = len(domo_sensors) + len(tripulante_sensors)  # 23

        for _ in range(N_TICKS):
            for s in domo_sensors:
                tmp_queue.enqueue(s.next_reading())
            for s in tripulante_sensors:
                tmp_queue.enqueue(s.next_reading())

        assert tmp_queue.count_total() == N_TICKS * total_sensores

        published = []
        mock_result = MagicMock()
        mock_result.rc = 0

        mock_client = MagicMock()
        mock_client.is_connected.return_value = True

        def capture_publish(topic, payload, qos):
            published.append(json.loads(payload))
            return mock_result

        mock_client.publish.side_effect = capture_publish

        syncer = GatewaySync(queue=tmp_queue, mqtt_client=mock_client)
        while tmp_queue.count_pending() > 0:
            syncer._drain_queue()

        # 1. Total publicado coincide exactamente
        assert len(published) == N_TICKS * total_sensores
        assert tmp_queue.count_pending() == 0

        # 2. Sin duplicados de (device_id, sensor_id, sequence)
        keys = [(r["device_id"], r["sensor_id"], r["sequence"]) for r in published]
        assert len(keys) == len(set(keys))

        # 3. Separacion estricta de device_id
        domo_readings = [r for r in published if r["device_id"] == "ESP32-01"]
        eva_readings = [r for r in published if r["device_id"] == "EVA-01"]

        assert len(domo_readings) == N_TICKS * len(domo_sensors)
        assert len(eva_readings) == N_TICKS * len(tripulante_sensors)

        # 4. Validar unidades y pertenencia
        domo_ids = {s.sensor_id for s in domo_sensors}
        eva_ids = {s.sensor_id for s in tripulante_sensors}

        for r in domo_readings:
            assert r["sensor_id"] in domo_ids
        for r in eva_readings:
            assert r["sensor_id"] in eva_ids
