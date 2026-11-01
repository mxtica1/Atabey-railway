"""
Simulador de sensor de temperatura del domo.

Publica lecturas realistas (15-35 C, variacion gradual) al topico MQTT
`atabey/domo/TEMP-01` cada 5 segundos, siguiendo el contrato de datos de
Mision Atabey exactamente.

Uso:
    pip install -r requirements.txt
    python simulate_temp.py

Variables de entorno (opcionales):
    MQTT_HOST   -- host del broker (default: localhost)
    MQTT_PORT   -- puerto del broker (default: 1883)
"""

import json
import os
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

# -- Configuracion -----------------------------------------------------------
BROKER_HOST: str = os.getenv("MQTT_HOST", "localhost")
BROKER_PORT: int = int(os.getenv("MQTT_PORT", "1883"))
TOPIC: str = "atabey/domo/TEMP-01"
DEVICE_ID: str = "ESP32-01"
SENSOR_ID: str = "TEMP-01"
INTERVAL_SECONDS: float = 5.0

TEMP_MIN: float = 15.0
TEMP_MAX: float = 35.0
TEMP_START: float = 25.0   # valor inicial (midpoint)
TEMP_STEP: float = 0.5     # variacion maxima por lectura (C)


# -- Helpers -----------------------------------------------------------------
def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def on_connect(client, userdata, connect_flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"[MQTT] Conexion fallida: {reason_code}")
    else:
        print(f"[MQTT] Conectado al broker {BROKER_HOST}:{BROKER_PORT}")


# -- Main --------------------------------------------------------------------
def main() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect

    # Reintentos de conexion
    for attempt in range(10):
        try:
            client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
            break
        except Exception as exc:
            wait = 3 * (attempt + 1)
            print(f"[MQTT] Intento {attempt + 1}/10 fallido: {exc}. Reintentando en {wait}s...")
            time.sleep(wait)
    else:
        raise SystemExit("No se pudo conectar al broker MQTT despues de 10 intentos.")

    client.loop_start()

    temperature: float = TEMP_START
    sequence: int = 1

    print(f"Simulador iniciado -> topico: {TOPIC}  |  intervalo: {INTERVAL_SECONDS}s")

    try:
        while True:
            # Random walk acotado: +/-TEMP_STEP por lectura
            delta = random.uniform(-TEMP_STEP, TEMP_STEP)
            temperature = clamp(temperature + delta, TEMP_MIN, TEMP_MAX)

            payload = {
                "device_id": DEVICE_ID,
                "sensor_id": SENSOR_ID,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "value": round(temperature, 2),
                "unit": "C",
                "sequence": sequence,
            }

            result = client.publish(TOPIC, json.dumps(payload), qos=1)
            status = "OK" if result.rc == mqtt.MQTT_ERR_SUCCESS else f"ERR rc={result.rc}"
            print(
                f"[{payload['timestamp']}] {SENSOR_ID}: {payload['value']:5.2f} C  "
                f"seq={sequence:5d}  {status}"
            )

            sequence += 1
            time.sleep(INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nSimulador detenido por el usuario.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
