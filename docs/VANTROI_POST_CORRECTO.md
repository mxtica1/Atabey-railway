# ⚠️ IMPORTANTE: Cómo hacer POST desde ESP32 (No desde navegador)

**Problema:** Si intentas acceder a `https://atabey-backend-k7kh.onrender.com/readings/batch` desde el navegador, ves **"Method Not Allowed"** porque el navegador intenta GET, pero el endpoint solo acepta **POST**.

---

## ❌ Esto NO funciona (GET desde navegador)
```
https://atabey-backend-k7kh.onrender.com/readings/batch
→ Error: Method Not Allowed (el navegador intenta GET)
```

## ✅ Esto sí funciona (POST desde código)

### 🔧 Desde Arduino (ESP32)

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

void sendTelemetry() {
  if (!WiFi.connected()) return;
  
  HTTPClient http;
  http.begin("https://atabey-backend-k7kh.onrender.com/readings/batch");
  http.addHeader("Content-Type", "application/json");
  
  // Crear JSON con buffer
  StaticJsonDocument<512> doc;
  doc["device_id"] = "ESP32-01";
  doc["buffer_id"] = "BUFFER-" + String(millis());
  
  JsonArray readings = doc.createNestedArray("readings");
  JsonObject reading = readings.createNestedObject();
  reading["sensor_id"] = "TEMP-01";
  reading["timestamp"] = "2026-11-06T20:15:00Z";
  reading["value"] = 25.5;
  reading["unit"] = "C";
  reading["sequence"] = 1;
  
  String jsonString;
  serializeJson(doc, jsonString);
  
  // IMPORTANTE: Usar POST, no GET
  int httpCode = http.POST(jsonString);
  
  if (httpCode == 200) {
    Serial.println("✓ Datos enviados");
  } else {
    Serial.printf("✗ Error: %d\n", httpCode);
  }
  
  http.end();
}
```

### 🧪 Desde Terminal (curl - POST)

```bash
curl -X POST https://atabey-backend-k7kh.onrender.com/readings/batch \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "ESP32-01",
    "buffer_id": "BUFFER-001",
    "readings": [
      {
        "sensor_id": "TEMP-01",
        "timestamp": "2026-11-06T20:15:00Z",
        "value": 25.5,
        "unit": "C",
        "sequence": 1
      }
    ]
  }'
```

### 🐍 Desde Python

```python
import requests
import json

url = "https://atabey-backend-k7kh.onrender.com/readings/batch"
headers = {"Content-Type": "application/json"}

data = {
    "device_id": "ESP32-01",
    "buffer_id": "BUFFER-001",
    "readings": [
        {
            "sensor_id": "TEMP-01",
            "timestamp": "2026-11-06T20:15:00Z",
            "value": 25.5,
            "unit": "C",
            "sequence": 1
        }
    ]
}

response = requests.post(url, json=data, headers=headers)
print(response.status_code)
print(response.json())
```

### 🔌 Desde JavaScript (Node.js o navegador)

```javascript
const url = 'https://atabey-backend-k7kh.onrender.com/readings/batch';
const data = {
  device_id: 'ESP32-01',
  buffer_id: 'BUFFER-001',
  readings: [
    {
      sensor_id: 'TEMP-01',
      timestamp: '2026-11-06T20:15:00Z',
      value: 25.5,
      unit: 'C',
      sequence: 1
    }
  ]
};

fetch(url, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data)
})
  .then(res => res.json())
  .then(ack => console.log('✓ ACK:', ack))
  .catch(err => console.error('✗ Error:', err));
```

---

## 📋 Estructura JSON Requerida

```json
{
  "device_id": "ESP32-01",        // ID del dispositivo
  "buffer_id": "BUFFER-001",      // ID único del lote
  "readings": [                    // Array de lecturas
    {
      "sensor_id": "TEMP-01",     // ID del sensor
      "timestamp": "2026-11-06T20:15:00Z",  // ISO 8601 UTC
      "value": 25.5,              // Valor numérico
      "unit": "C",                // Unidad
      "sequence": 1               // Contador incremental
    }
  ]
}
```

---

## ✅ Respuesta Esperada (HTTP 200)

```json
{
  "buffer_id": "BUFFER-001",
  "device_id": "ESP32-01",
  "accepted": 1,
  "duplicates": 0,
  "rejected": 0,
  "items": [
    {
      "sensor_id": "TEMP-01",
      "sequence": 1,
      "status": "ok",
      "reading_id": 12345,
      "timestamp": "2026-11-06T20:15:00Z"
    }
  ]
}
```

---

## 🔍 Checklist

- [ ] **Método:** POST (no GET)
- [ ] **URL:** `https://atabey-backend-k7kh.onrender.com/readings/batch`
- [ ] **Header:** `Content-Type: application/json`
- [ ] **JSON válido:** Estructura exacta arriba
- [ ] **device_id:** Presente y consistente
- [ ] **buffer_id:** Único por lote
- [ ] **readings:** Array (aunque sea 1 elemento)
- [ ] **timestamp:** ISO 8601 UTC formato

¡Listo!

