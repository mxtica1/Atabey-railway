"""
Generadores de sensores del domo -- Mision Atabey.

Cada SensorGenerator encapsula:
- Identificadores del contrato (device_id, sensor_id, unit)
- Rango de valores validos y paso maximo (random walk acotado)
- Estado interno: valor actual y contador sequence PROPIO (nunca compartido)

Todos los sensores del domo comparten el mismo device_id (ESP32 del domo).

Supuestos pendientes de confirmar con hardware antes del Modulo 5:
  NPK-*       No hay sensor fisico documentado; se simula para el dashboard.
  SOIL-TEMP-* El STEMMA Soil mide temperatura y humedad en la misma lectura
              fisica; se modela con un sensor_id por magnitud.
  LUX-01      Renombrado desde UV-01; el TSL2591 mide lux (visible+IR), no UV.
"""

import random
from datetime import datetime, timezone

DEVICE_ID: str = "ESP32-01"


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class SensorGenerator:
    """
    Generador de lecturas para un sensor del domo con random walk acotado.

    El sequence empieza en 1 y es independiente por instancia: nunca se
    comparte con ninguna otra instancia de SensorGenerator.
    """

    def __init__(
        self,
        sensor_id: str,
        unit: str,
        value_min: float,
        value_max: float,
        step: float,
    ) -> None:
        self.sensor_id = sensor_id
        self.unit = unit
        self.value_min = value_min
        self.value_max = value_max
        self.step = step
        # Estado interno
        self._current: float = (value_min + value_max) / 2.0
        self._sequence: int = 1

    def next_reading(self) -> dict:
        """Genera la siguiente lectura siguiendo el contrato de datos de AGENTS.md."""
        delta = random.uniform(-self.step, self.step)
        self._current = _clamp(
            self._current + delta, self.value_min, self.value_max
        )
        reading = {
            "device_id": DEVICE_ID,
            "sensor_id": self.sensor_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "value": round(self._current, 2),
            "unit": self.unit,
            "sequence": self._sequence,
        }
        self._sequence += 1
        return reading

    def __repr__(self) -> str:
        return (
            f"SensorGenerator({self.sensor_id!r}, unit={self.unit!r}, "
            f"range=[{self.value_min}, {self.value_max}])"
        )


# ---------------------------------------------------------------------------
# Fabrica de sensores del domo
# ---------------------------------------------------------------------------

def make_domo_sensors() -> list:
    """
    Devuelve instancias FRESCAS (sequence=1) de todos los sensores del domo.

    Cada llamada devuelve generadores con estado limpio. Usar esta funcion
    (no DOMO_SENSORS directamente) en LoRaReceiverSim para garantizar
    sequences que empiezan en 1 en cada ejecucion.
    """
    return [
        #  sensor_id          unit       min      max    step
        SensorGenerator("TEMP-01",      "C",      15.0,   35.0,   0.5),
        SensorGenerator("HUM-01",       "%",      40.0,   85.0,   1.0),
        SensorGenerator("CO2-01",       "ppm",   400.0, 1200.0,  10.0),
        SensorGenerator("LUX-01",       "lux",   100.0, 3000.0,  50.0),
        SensorGenerator("SOIL-HUM-01",  "%",      20.0,   70.0,   0.8),
        SensorGenerator("SOIL-HUM-02",  "%",      20.0,   70.0,   0.8),
        SensorGenerator("SOIL-HUM-03",  "%",      20.0,   70.0,   0.8),
        SensorGenerator("SOIL-TEMP-01", "C",      15.0,   30.0,   0.3),
        SensorGenerator("SOIL-TEMP-02", "C",      15.0,   30.0,   0.3),
        SensorGenerator("SOIL-TEMP-03", "C",      15.0,   30.0,   0.3),
        SensorGenerator("NPK-N-01",     "mg/kg",  50.0,  300.0,   3.0),
        SensorGenerator("NPK-P-01",     "mg/kg",  20.0,  150.0,   2.0),
        SensorGenerator("NPK-K-01",     "mg/kg", 100.0,  400.0,   4.0),
    ]


# Instancia de referencia (para inspeccion, parametrizacion de tests, etc.)
DOMO_SENSORS: list = make_domo_sensors()
