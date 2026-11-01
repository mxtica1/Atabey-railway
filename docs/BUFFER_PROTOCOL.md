# Protocolo de buffer de datos y ACK — Misión Atabey 1

**Implementación:** `backend/mqtt_client.py` (`ingest_batch`, `publish_ack`) · `backend/main.py` (`POST /readings/batch`)

Este documento explica cómo enviar un **buffer de datos** desde el ESP32/firmware
y cómo la computadora **confirma que lo recibió**.

---

## 1. El problema que resuelve

El ESP32 acumula lecturas en un buffer (por ejemplo: 5 sensores × 12 lecturas = 60
lecturas) y las envía de una vez. Necesitas saber:

1. **Que el buffer llegó** → confirmación (ACK).
2. **Que se guardó cada lectura** → un ACK por item, con `sensor_id` y `received_at`.
3. **Cuándo se guardó y de qué sensor vino** → registro de ingesta consultable.

---

## 2. Formato del buffer

```json
{
  "device_id": "ESP32-01",
  "buffer_id": "buf-2026-10-31-000123",
  "sent_at": "2026-10-31T18:00:05Z",
  "readings": [
    {
      "device_id": "ESP32-01",
      "sensor_id": "TEMP-01",
      "timestamp": "2026-10-31T18:00:00Z",
      "value": 28.4,
      "unit": "C",
      "sequence": 1542
    },
    {
      "device_id": "ESP32-01",
      "sensor_id": "HUM-01",
      "timestamp": "2026-10-31T18:00:00Z",
      "value": 62.1,
      "unit": "%",
      "sequence": 891
    }
  ]
}
```

| Campo | Obligatorio | Regla |
|---|---|---|
| `device_id` | sí | `ESP32-01` o `EVA-01` |
| `buffer_id` | sí | **único por envío**. Es la clave de idempotencia (ver §5) |
| `sent_at` | no | ISO-8601 UTC, momento del envío |
| `readings` | sí | ≥ 1 lectura, cada una con el contrato de lectura de AGENTS.md |

---

## 3. Dos vías de envío

### 3.1 MQTT (recomendado — es el canal del proyecto)

**Publica en:** `atabey/{device_id}/buffer`

```
atabey/ESP32-01/buffer
atabey/EVA-01/buffer
```

QoS 1 recomendado.

### 3.2 REST (si el ESP32 tiene HTTP)

```bash
curl -X POST http://<backend>/readings/batch \
  -H "Content-Type: application/json" \
  -d @buffer.json
```

Respuesta = el mismo ACK que llega por MQTT.

---

## 4. El ACK (confirmación)

### 4.1 Por MQTT — topico `atabey/ack/{device_id}`

```
atabey/ack/ESP32-01
```

```json
{
  "type": "ack",
  "device_id": "ESP32-01",
  "buffer_id": "buf-2026-10-31-000123",
  "received_at": "2026-10-31T18:00:07.412Z",
  "accepted": 2,
  "rejected": 0,
  "duplicates": 0,
  "items": [
    {
      "sensor_id": "TEMP-01",
      "sequence": 1542,
      "status": "stored",
      "received_at": "2026-10-31T18:00:07.390Z",
      "db_id": 4211,
      "error": null
    },
    {
      "sensor_id": "HUM-01",
      "sequence": 891,
      "status": "stored",
      "received_at": "2026-10-31T18:00:07.391Z",
      "db_id": 4212,
      "error": null
    }
  ]
}
```

### 4.2 Campos del ACK

| Campo | Significado |
|---|---|
| `received_at` | **cuándo la computadora confirmó** (UTC del servidor) |
| `accepted` | lecturas guardadas correctamente |
| `rejected` | lecturas rechazadas por esquema inválido |
| `duplicates` | lecturas que ya estaban guardadas (buffer reenviado) |
| `items[].sensor_id` | **de qué sensor vino** cada dato |
| `items[].sequence` | el sequence del sensor en esa lectura |
| `items[].status` | `stored` \| `duplicate` \| `rejected` |
| `items[].received_at` | **cuándo se guardó** esa lectura concreta |
| `items[].db_id` | id en PostgreSQL (traza completa) |
| `items[].error` | motivo si fue rechazada |

### 4.3 Lógica en el firmware

```c
// tras publicar el buffer
if (ack.received && ack.accepted == lecturas_enviadas) {
    //.buffer vaciado — se puede limpiar la flash
} else if (ack.duplicates > 0) {
    // ya estaba guardado — reintentar solo los faltantes
} else {
    // reintentar el buffer completo
}
```

---

## 5. Idempotencia

Si el mismo `buffer_id` se reenvía (porque el ACK no llegó y el firmware reintenta):

- **No se duplica ninguna lectura.**
- Se devuelve el ACK original con `status: "duplicate"` en cada item.
- `accepted` = 0, `duplicates` = N.

Esto permite reintentar sin miedo.

---

## 6. Atomicidad

Todo el buffer se guarda en **una transacción**. Si algo falla a la mitad, no se
guarda nada y el firmware puede reenviar el buffer completo.

---

## 7. Umbrales y alertas

Cada lectura del buffer pasa por **el mismo ciclo de umbral/alerta** que una
lectura individual:

- Si el valor sale del umbral, se crea/actualiza una alerta.
- Severidad: `critico` si se pasa el umbral en más del 20 % del rango,
  `advertencia` si no.
- Si vuelve a rango, la alerta activa se auto-resuelve.

**No hay que hacer nada especial en el firmware** — las alertas funcionan igual
enviando lecturas individuales o un buffer completo.

---

## 8. Consultar el registro de ingesta

```bash
curl "http://localhost:8000/ingest/recent?limit=100"
```

```json
{
  "total": 2,
  "generated_at": "2026-10-31T18:00:10Z",
  "buffers": [
    {
      "buffer_id": "buf-2026-10-31-000123",
      "device_id": "ESP32-01",
      "received_at": "2026-10-31T18:00:07.412Z",
      "readings": 2,
      "sensors": ["TEMP-01", "HUM-01"]
    }
  ],
  "records": [
    {
      "id": 4211,
      "device_id": "ESP32-01",
      "sensor_id": "TEMP-01",
      "value": 28.4,
      "unit": "C",
      "timestamp": "2026-10-31T18:00:00Z",
      "received_at": "2026-10-31T18:00:07.390Z",
      "buffer_id": "buf-2026-10-31-000123",
      "sequence": 1542
    }
  ]
}
```

- `timestamp` → cuándo midió el sensor.
- `received_at` → cuándo lo guardó la computadora.
- `sensor_id` → de qué sensor vino.
- `buffer_id` → a qué envío pertenece.

En el dashboard está en la vista **Registro de ingesta** (icono de base de datos
en la barra lateral).

---

## 9. Ejemplo end-to-end (Python)

```python
import json, time, uuid
import paho.mqtt.client as mqtt

def make_buffer(device_id, samples):
    """samples: lista de dicts {sensor_id, value, unit, sequence}"""
    return {
        "device_id": device_id,
        "buffer_id": f"buf-{uuid.uuid4().hex[:12]}",
        "sent_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "readings": [
            {
                "device_id": device_id,
                "sensor_id": s["sensor_id"],
                "timestamp": s["timestamp"],
                "value": s["value"],
                "unit": s["unit"],
                "sequence": s["sequence"],
            }
            for s in samples
        ],
    }

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_message = lambda c, u, m: print("ACK:", m.payload.decode())

client.connect("localhost", 1883)
client.subscribe("atabey/ack/ESP32-01")
client.loop_start()

buffer_ = make_buffer("ESP32-01", mis_lecturas)
client.publish("atabey/ESP32-01/buffer", json.dumps(buffer_), qos=1)
```

---

## 10. Resumen de tópicos MQTT

| Tópico | Dirección | Contenido |
|---|---|---|
| `atabey/{group}/{sensor_id}` | ESP32 → servidor | lectura individual (contrato de AGENTS.md) |
| `atabey/{device_id}/buffer` | ESP32 → servidor | buffer de datos |
| `atabey/ack/{device_id}` | servidor → ESP32 | confirmación del buffer |
| `atabey/{device_id}/location` | ESP32 → servidor | posición GPS del tripulante |
| `atabey/#` | servidor → dashboard (WS) | lectura, alerta, location, ingest |
