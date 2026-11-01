"""
Cliente de prueba del protocolo de BUFFER DE DATOS — Mision Atabey.

Simula al ESP32/firmware: arma un buffer con lecturas reales (o de ejemplo),
lo publica por MQTT y ESPERA el ACK en `atabey/ack/{device_id}` para confirmar
que la computadora lo recibio y guardo.

Uso:
    # enviar un buffer de ejemplo del domo
    python send_buffer.py

    # enviar lecturas concretas por JSON
    python send_buffer.py --json '[{"sensor_id":"TEMP-01","value":28.4,"unit":"C","sequence":1}]'

    # solo monitorear los ACKs que lleguen
    python send_buffer.py --listen

Variables de entorno (opcionales):
    MQTT_HOST  -- host del broker (default: localhost)
    MQTT_PORT  -- puerto del broker (default: 1883)
    EVA_DEVICE -- device_id del emisor (default: ESP32-01)
    WAIT_SECS  -- segundos de espera del ACK (default: 15)

Ver `docs/BUFFER_PROTOCOL.md` para el detalle del protocolo.
"""

import argparse
import json
import os
import sys
import threading
import time
import uuid

import paho.mqtt.client as mqtt

BROKER_HOST: str = os.getenv("MQTT_HOST", "localhost")
BROKER_PORT: int = int(os.getenv("MQTT_PORT", "1883"))
DEVICE_ID: str = os.getenv("EVA_DEVICE", "ESP32-01")
WAIT_SECS: float = float(os.getenv("WAIT_SECS", "15"))

BUFFER_TOPIC = f"atabey/{DEVICE_ID}/buffer"
ACK_TOPIC = f"atabey/ack/{DEVICE_ID}"

# Lecturas de ejemplo: sensor_id, value, unit, sequence
SAMPLE_READINGS = [
    {"sensor_id": "TEMP-01",      "value": 28.4,  "unit": "C",     "sequence": 1542},
    {"sensor_id": "HUM-01",       "value": 62.1,  "unit": "%",     "sequence": 891},
    {"sensor_id": "CO2-01",       "value": 850.0, "unit": "ppm",   "sequence": 301},
    {"sensor_id": "LUX-01",       "value": 1240.0,"unit": "lux",   "sequence": 122},
    {"sensor_id": "SOIL-HUM-01",  "value": 48.5,  "unit": "%",     "sequence": 77},
]


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_buffer(readings: list) -> dict:
    """Arma el buffer con el contrato de AGENTS.md."""
    ts = now_iso()
    return {
        "device_id": DEVICE_ID,
        "buffer_id": f"buf-{uuid.uuid4().hex[:12]}",
        "sent_at": ts,
        "readings": [
            {
                "device_id": DEVICE_ID,
                "sensor_id": r["sensor_id"],
                "timestamp": ts,
                "value": r["value"],
                "unit": r["unit"],
                "sequence": r["sequence"],
            }
            for r in readings
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Envia un buffer de datos y espera el ACK")
    parser.add_argument("--json", help="Lecturas en JSON: [{sensor_id,value,unit,sequence}]")
    parser.add_argument("--listen", action="store_true", help="Solo escuchar ACKs, no enviar")
    args = parser.parse_args()

    acks: list[tuple] = []
    ack_ready = threading.Event()

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"!! Conexion MQTT fallida: {reason_code}")
            return
        client.subscribe(ACK_TOPIC)
        client.subscribe("atabey/#")
        print(f"Conectado a {BROKER_HOST}:{BROKER_PORT} — escuchando {ACK_TOPIC}")

    def on_message(client, userdata, message):
        topic = str(message.topic)
        if not topic.startswith("atabey/ack/"):
            return
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except Exception:
            return
        acks.append((topic, payload))
        ack_ready.set()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(BROKER_HOST, BROKER_PORT, 60)
    except Exception as exc:
        print(f"!! No se pudo conectar al broker: {exc}")
        return 1
    client.loop_start()
    time.sleep(1.5)

    if args.listen:
        print("Esperando ACKs (Ctrl+C para salir)…")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        client.loop_stop()
        client.disconnect()
        return 0

    readings = json.loads(args.json) if args.json else SAMPLE_READINGS
    buffer_ = build_buffer(readings)

    print(f"\n-> Enviando buffer {buffer_['buffer_id']} con {len(buffer_['readings'])} lecturas")
    print(f"   topico: {BUFFER_TOPIC}")
    client.publish(BUFFER_TOPIC, json.dumps(buffer_), qos=1)

    print(f"   esperando ACK en {ACK_TOPIC} (max {WAIT_SECS}s)…")
    ack_ready.wait(timeout=WAIT_SECS)

    client.loop_stop()
    client.disconnect()

    if not acks:
        print("\n!! No llego ACK. Revisa que el backend este corriendo y suscrito a atabey/#")
        return 2

    topic, ack = acks[0]
    print(f"\n<- ACK recibido en {topic}")
    print(f"   buffer_id   : {ack['buffer_id']}")
    print(f"   received_at : {ack['received_at']}")
    print(f"   accepted    : {ack['accepted']}")
    print(f"   duplicates  : {ack['duplicates']}")
    print(f"   rejected    : {ack['rejected']}")
    print("   detalle por lectura:")
    for item in ack.get("items", []):
        print(
            f"     - {item['sensor_id']:<14} seq={item['sequence']:<6} "
            f"{item['status']:<10} db_id={item.get('db_id')} "
            f"guardado={item.get('received_at')}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
