"""
Generadores de sensores del tripulante (Mochila EVA) -- Mision Atabey.

Dispositivo: EVA-01 (mochila de soporte vital y biomecanica del tripulante).

Cada SensorGenerator encapsula:
- Identificadores del contrato (device_id, sensor_id, unit)
- Rango de valores validos y paso maximo (random walk acotado)
- Estado interno: valor actual y contador sequence PROPIO (nunca compartido)

Para ACTIVITY-01 se utiliza ActivitySensorGenerator, que produce codigos
categoricos enteros (0=Still, 1=Walking, 2=Running, 3=Tilting) sostenidos
entre 20 y 60 segundos antes de realizar una transicion.

Supuestos pendientes de hardware (Modulo 4):
  1. ECG crudo (AD8232) queda fuera (onda continua, no escalar).
  2. Giroscopio, magnetometro y cuaterniones del BNO055 quedan fuera en este corte.
  3. ACTIVITY-01 es categorico entero (0-3).
  4. Unico tripulante (EVA-01) en este corte.
"""

import random
from datetime import datetime, timezone
from typing import Union

DEVICE_ID: str = "EVA-01"

# Mapeo de estados de actividad (BNO055)
ACTIVITY_MAP = {
    0: "Still",
    1: "Walking",
    2: "Running",
    3: "Tilting",
}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class SensorGenerator:
    """
    Generador de lecturas para un sensor continuo del tripulante con random walk.

    El sequence empieza en 1 y es independiente por instancia: nunca se
    comparte con ninguna otra instancia.
    """

    def __init__(
        self,
        sensor_id: str,
        unit: str,
        value_min: float,
        value_max: float,
        step: float,
        device_id: str = DEVICE_ID,
        initial_value: float | None = None,
    ) -> None:
        self.sensor_id = sensor_id
        self.unit = unit
        self.value_min = value_min
        self.value_max = value_max
        self.step = step
        self.device_id = device_id
        # Estado interno
        if initial_value is not None:
            self._current = initial_value
        else:
            self._current = (value_min + value_max) / 2.0
        self._sequence: int = 1

    def next_reading(self) -> dict:
        """Genera la siguiente lectura siguiendo el contrato de datos."""
        delta = random.uniform(-self.step, self.step)
        self._current = _clamp(
            self._current + delta, self.value_min, self.value_max
        )
        reading = {
            "device_id": self.device_id,
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


class ActivitySensorGenerator:
    """
    Generador de lecturas para el sensor ACTIVITY-01 (estado de actividad BNO055).

    Genera enteros entre 0 y 3:
      0 = Still
      1 = Walking
      2 = Running
      3 = Tilting

    A diferencia de sensores continuos, sostiene el valor entre 20 y 60 segundos
    antes de cambiar a un nuevo estado, aunque continue emitiendo lecturas
    cada intervalo (5s por defecto).
    """

    def __init__(
        self,
        sensor_id: str = "ACTIVITY-01",
        unit: str = "código",
        device_id: str = DEVICE_ID,
        min_hold_seconds: float = 20.0,
        max_hold_seconds: float = 60.0,
        step_seconds: float = 5.0,
        initial_state: int = 0,
    ) -> None:
        self.sensor_id = sensor_id
        self.unit = unit
        self.device_id = device_id
        self.value_min = 0
        self.value_max = 3
        self.min_hold_seconds = min_hold_seconds
        self.max_hold_seconds = max_hold_seconds
        self.step_seconds = step_seconds

        self._current_state: int = initial_state
        self._hold_seconds_remaining: float = random.uniform(
            min_hold_seconds, max_hold_seconds
        )
        self._sequence: int = 1

    def next_reading(self, elapsed_seconds: float | None = None) -> dict:
        """Genera la siguiente lectura manteniendo el estado o transicionando."""
        delta_t = self.step_seconds if elapsed_seconds is None else elapsed_seconds

        reading = {
            "device_id": self.device_id,
            "sensor_id": self.sensor_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "value": self._current_state,
            "unit": self.unit,
            "sequence": self._sequence,
        }
        self._sequence += 1

        self._hold_seconds_remaining -= delta_t
        if self._hold_seconds_remaining <= 0:
            choices = [s for s in (0, 1, 2, 3) if s != self._current_state]
            self._current_state = random.choice(choices)
            self._hold_seconds_remaining = random.uniform(
                self.min_hold_seconds, self.max_hold_seconds
            )

        return reading

    def __repr__(self) -> str:
        return (
            f"ActivitySensorGenerator({self.sensor_id!r}, "
            f"hold=[{self.min_hold_seconds}s, {self.max_hold_seconds}s])"
        )


# ---------------------------------------------------------------------------
# Fabrica de sensores del tripulante
# ---------------------------------------------------------------------------

def make_tripulante_sensors() -> list[Union[SensorGenerator, ActivitySensorGenerator]]:
    """
    Devuelve instancias FRESCAS (sequence=1) de los 10 sensores de la mochila EVA.
    """
    return [
        # Biometricos
        SensorGenerator("HR-01",        "bpm",   55.0,  140.0,  1.5, initial_value=75.0),
        SensorGenerator("SPO2-01",      "%",     92.0,  100.0,  0.3, initial_value=98.0),
        SensorGenerator("BTEMP-01",     "C",     34.5,   37.5,  0.1, initial_value=36.6),
        # Ambientales mochila
        SensorGenerator("EVA-TEMP-01",  "C",     15.0,   35.0,  0.5, initial_value=24.0),
        SensorGenerator("EVA-HUM-01",   "%",     30.0,   70.0,  1.0, initial_value=45.0),
        SensorGenerator("EVA-PRESS-01", "hPa",  950.0, 1030.0,  1.0, initial_value=1013.25),
        # Aceleracion 3 ejes (BNO055 compensada)
        SensorGenerator("ACC-X-01",     "m/s²",  -3.0,    3.0,  0.2, initial_value=0.0),
        SensorGenerator("ACC-Y-01",     "m/s²",  -3.0,    3.0,  0.2, initial_value=0.0),
        SensorGenerator("ACC-Z-01",     "m/s²",  -3.0,    3.0,  0.2, initial_value=0.0),
        # Estado de actividad sostenido
        ActivitySensorGenerator("ACTIVITY-01", unit="código"),
    ]


TRIPULANTE_SENSORS: list = make_tripulante_sensors()
