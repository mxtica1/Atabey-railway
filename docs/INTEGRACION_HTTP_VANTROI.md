# 🛰️ Guía de Integración: Vantroi → Atabey Dashboard (HTTP POST)

## URL del Servidor

```
🔗 https://mayflower-motto-sublime.ngrok-free.dev
```

Usa esta URL para enviar datos desde Vantroi. **No requiere autenticación.**

---

## Endpoint: Enviar Datos

### HTTP POST
```
POST https://mayflower-motto-sublime.ngrok-free.dev/readings/batch
Content-Type: application/json
```

### Formato del Body

```json
{
  "device_id": "VANTROI-01",
  "buffer_id": "buf-001",
  "readings": [
    {
      "sensor_id": "TEMP-01",
      "value": 28.4,
      "unit": "C",
      "timestamp": "2026-10-31T20:15:00Z",
      "sequence": 1
    },
    {
      "sensor_id": "HR-01",
      "value": 75,
      "unit": "bpm",
      "timestamp": "2026-10-31T20:15:00Z",
      "sequence": 2
    }
  ]
}
```

### Campos Requeridos

| Campo | Tipo | Ejemplo | Obligatorio |
|-------|------|---------|------------|
| `device_id` | string | `VANTROI-01`, `ESP32-VANTROI` | ✓ Sí |
| `buffer_id` | string | `buf-001`, `buffer-1730390100` | ✓ Sí |
| `readings[].sensor_id` | string | `TEMP-01`, `HR-01`, `SPO2-01` | ✓ Sí |
| `readings[].value` | number | `28.4`, `75`, `98` | ✓ Sí |
| `readings[].unit` | string | `C`, `bpm`, `%` | ✓ Sí |
| `readings[].timestamp` | string (ISO 8601) | `2026-10-31T20:15:00Z` | ✓ Sí |
| `readings[].sequence` | integer | `1`, `2`, `3` | ✓ Sí (para detectar pérdidas) |

---

## Respuesta Esperada (HTTP 200)

```json
{
  "buffer_id": "buf-001",
  "device_id": "VANTROI-01",
  "accepted": 2,
  "duplicates": 0,
  "rejected": 0,
  "acks": [
    {
      "sensor_id": "TEMP-01",
      "reading_id": 1,
      "sequence": 1,
      "timestamp": "2026-10-31T20:15:00Z"
    },
    {
      "sensor_id": "HR-01",
      "reading_id": 2,
      "sequence": 2,
      "timestamp": "2026-10-31T20:15:00Z"
    }
  ]
}
```

---

## Ejemplo Arduino / ESP32

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

const char* WIFI_SSID = "tu_ssid";
const char* WIFI_PASS = "tu_contrasena";
const char* SERVER = "mayflower-motto-sublime.ngrok-free.dev";
const char* DEVICE_ID = "VANTROI-01";  // O el nombre que prefieras

WiFiClient client;
HTTPClient http;

void sendReading(float temperature, int heartRate) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi no conectado");
    return;
  }

  // Crear JSON
  DynamicJsonDocument doc(512);
  doc["device_id"] = DEVICE_ID;
  doc["buffer_id"] = String("buf-") + millis();
  
  JsonArray readings = doc.createNestedArray("readings");
  
  // Lectura 1: Temperatura
  JsonObject reading1 = readings.createNestedObject();
  reading1["sensor_id"] = "TEMP-01";
  reading1["value"] = temperature;
  reading1["unit"] = "C";
  reading1["timestamp"] = getISOTimestamp();  // Timestamp ISO 8601
  reading1["sequence"] = 1;
  
  // Lectura 2: Pulso
  JsonObject reading2 = readings.createNestedObject();
  reading2["sensor_id"] = "HR-01";
  reading2["value"] = heartRate;
  reading2["unit"] = "bpm";
  reading2["timestamp"] = getISOTimestamp();
  reading2["sequence"] = 2;
  
  // Serializar
  String payload;
  serializeJson(doc, payload);
  
  // Enviar POST
  String url = "https://" + String(SERVER) + "/readings/batch";
  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");
  
  int httpCode = http.POST(payload);
  
  if (httpCode == 200) {
    String response = http.getString();
    Serial.println("✓ Datos enviados correctamente");
    Serial.println(response);
  } else {
    Serial.print("✗ Error HTTP: ");
    Serial.println(httpCode);
  }
  
  http.end();
}

String getISOTimestamp() {
  // Retorna timestamp en formato ISO 8601, ej: 2026-10-31T20:15:00Z
  // Implementa usando NTP o RTC según tu ESP32
  return "2026-10-31T20:15:00Z";
}

void setup() {
  Serial.begin(115200);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  delay(2000);
}

void loop() {
  // Cada 5 segundos, envía una lectura
  float temp = readTemperature();  // Tu función de lectura
  int hr = readHeartRate();        // Tu función de lectura
  
  sendReading(temp, hr);
  delay(5000);
}
```

---

## Sensores Válidos en Atabey

Puedes usar cualquier `sensor_id` de esta lista:

### Domo (Ambiente)
- `TEMP-01` — Temperatura aire (°C)
- `HUM-01` — Humedad relativa aire (%)
- `CO2-01` — CO₂ (ppm)
- `O2-01` — O₂ (%)
- `LUX-01` — Luz (lux)

### Suelo
- `SOIL-HUM-01` — Humedad suelo (%)
- `SOIL-TEMP-01` — Temperatura suelo (°C)

### Nutrientes
- `NPK-N-01` — Nitrógeno (mg/L)
- `NPK-P-01` — Fósforo (mg/L)
- `NPK-K-01` — Potasio (mg/L)

### Tripulante
- `HR-01` — Pulso cardíaco (bpm)
- `SPO2-01` — Oxigenación sangre (%)
- `BTEMP-01` — Temperatura corporal (°C)
- `SUIT-TEMP-01` — Temperatura traje de soporte vital (°C)
- `WATER-01` — Agua potable en mochila (%)
- `ACC-X-01`, `ACC-Y-01`, `ACC-Z-01` — Aceleración lineal (m/s²)
- `ACTIVITY-01` — Estado de actividad (0=Still, 1=Walking, 2=Running, 3=Tilting)

---

## Dashboard en Vivo

Una vez que Vantroi envíe datos, aparecerán **automáticamente** en el dashboard:

```
📊 http://localhost:5173  (acceso local)
```

**Lo que verás:**
- Lecturas en tiempo real de todos los sensores
- Historial de datos
- Alertas si algún valor sale de rango
- Ubicación del tripulante en el mapa

---

## Troubleshooting

### ❌ "Connection refused"
- Verifica que el túnel ngrok está corriendo: `ngrok http 8000`
- Verifica que el backend está en puerto 8000

### ❌ "404 Not Found"
- Usa exactamente: `/readings/batch` (no `/reading/batch` ni `/data`)
- Verifica que es `POST`, no `GET`

### ❌ "CORS error"
- El servidor acepta solicitudes desde cualquier origen en modo anónimo

### ❌ "Invalid JSON"
- Revisa que todos los campos requeridos estén presentes
- Verifica que `timestamp` sea ISO 8601 válido: `YYYY-MM-DDTHH:MM:SSZ`

### ❌ Datos no aparecen en dashboard
- Espera 5 segundos (intervalo de actualización WebSocket)
- Abre browser console (F12) y busca mensajes de error
- Verifica que el `device_id` sea consistente

---

## Modo Prueba: cURL

Prueba el endpoint desde terminal:

```bash
curl -X POST https://mayflower-motto-sublime.ngrok-free.dev/readings/batch \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "VANTROI-TEST",
    "buffer_id": "test-1",
    "readings": [
      {
        "sensor_id": "TEMP-01",
        "value": 28.4,
        "unit": "C",
        "timestamp": "2026-10-31T20:15:00Z",
        "sequence": 1
      }
    ]
  }'
```

Deberías recibir:
```json
{"buffer_id":"test-1","device_id":"VANTROI-TEST","accepted":1,"duplicates":0,"rejected":0,...}
```

---

## ¿Preguntas?

- **¿Qué timestamps usar?** ISO 8601 con UTC (termina en `Z`). Ej: `2026-10-31T20:15:00Z`
- **¿Secuencia?** Incrementa para cada lectura del mismo sensor. Detecta pérdidas de paquetes.
- **¿Buffer ID?** Identificador único por lote. Atabey ignora duplicados (idempotencia).
- **¿Autenticación?** No necesaria en modo anónimo.

**¡Listo para empezar!** 🚀
