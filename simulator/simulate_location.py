"""
Simulador de posicion GPS del tripulante EVA-01.

Genera un "random walk" acotado alrededor de las coordenadas base de la
Reserva Cientifica Ebano Verde, Constanza, Republica Dominicana
(placeholder — reemplazar con las coordenadas reales del sitio cuando
esten disponibles).

Publica cada 5 segundos al topico MQTT:
    atabey/eva/EVA-01/location

Payload (entidad LocationUpdate, separada de SensorReading):
{
    "device_id": "EVA-01",
    "timestamp": "2026-09-24T20:15:00Z",
    "lat": 18.8776,
    "lon": -70.5609,
    "sequence": 1,
    "sexo": "F"
}

Uso:
    pip install -r requirements.txt
    python simulate_location.py

Variables de entorno (opcionales):
    MQTT_HOST    -- host del broker (default: localhost)
    MQTT_PORT    -- puerto del broker (default: 1883)
    EVA_DEVICE   -- device_id (default: EVA-01)
    EVA_SEXO     -- sexo del tripulante "M" | "F" (default: "F")
    LOC_INTERVAL -- intervalo en segundos (default: 5.0)
"""

import json
import os
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

# ── Configuracion ─────────────────────────────────────────────────────────────

BROKER_HOST: str   = os.getenv("MQTT_HOST",    "localhost")
BROKER_PORT: int   = int(os.getenv("MQTT_PORT", "1883"))
DEVICE_ID: str     = os.getenv("EVA_DEVICE",   "EVA-01")
EVA_SEXO_RAW: str  = os.getenv("EVA_SEXO",     "F")
INTERVAL: float    = float(os.getenv("LOC_INTERVAL", "5.0"))

# Normaliza el valor de sexo: solo "M" o "F" son validos; cualquier otra cosa -> None
EVA_SEXO = EVA_SEXO_RAW.upper() if EVA_SEXO_RAW.upper() in ("M", "F") else None

# Coordenadas base — Ebano Verde, Constanza, RD (placeholder)
BASE_LAT: float = 18.8776
BASE_LON: float = -70.5609

# Radio maximo del random walk (~50 m en grados)
STEP_DEG: float = 0.0005  # ~55 m por paso

# Topico MQTT: atabey/eva/{device_id}/location
TOPIC: str = f"atabey/eva/{DEVICE_ID}/location"


# ── Helpers ───────────────────────────────────────────────────────────────────

def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def on_connect(client, userdata, connect_flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"[MQTT] Conexion fallida: {reason_code}")
    else:
        print(f"[MQTT] Conectado al broker {BROKER_HOST}:{BROKER_PORT}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect

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

    lat: float = BASE_LAT
    lon: float = BASE_LON
    sequence:  int = 1

    # Acota el random walk a un radio ~500 m del punto base
    MAX_OFFSET = 0.0045  # ~500 m

    print(f"Simulador de posicion iniciado")
    print(f"  Dispositivo : {DEVICE_ID}")
    print(f"  Sexo        : {EVA_SEXO or '(no especificado)'}")
    print(f"  Topico      : {TOPIC}")
    print(f"  Base        : ({BASE_LAT}, {BASE_LON})")
    print(f"  Intervalo   : {INTERVAL}s")

    try:
        while True:
            # Random walk acotado alrededor de la base
            lat = clamp(lat + random.uniform(-STEP_DEG, STEP_DEG),
                        BASE_LAT - MAX_OFFSET, BASE_LAT + MAX_OFFSET)
            lon = clamp(lon + random.uniform(-STEP_DEG, STEP_DEG),
                        BASE_LON - MAX_OFFSET, BASE_LON + MAX_OFFSET)

            payload = {
                "device_id": DEVICE_ID,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "lat":       round(lat, 6),
                "lon":       round(lon, 6),
                "sequence":  sequence,
            }
            if EVA_SEXO is not None:
                payload["sexo"] = EVA_SEXO

            result = client.publish(TOPIC, json.dumps(payload), qos=1)
            status = "OK" if result.rc == mqtt.MQTT_ERR_SUCCESS else f"ERR rc={result.rc}"
            print(
                f"[{payload['timestamp']}] {DEVICE_ID}: "
                f"({payload['lat']:.6f}, {payload['lon']:.6f})  "
                f"seq={sequence:5d}  {status}"
            )

            sequence += 1
            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        print("\nSimulador de posicion detenido.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
