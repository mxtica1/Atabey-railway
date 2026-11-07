# ✅ SOLUCIÓN: Endpoint para Lecturas Individuales

**Fecha:** 6 Nov 2026 - 21:45 UTC  
**Para:** Vantroi  
**Asunto:** Ya NO necesitas agrupar en arrays - puedes enviar una lectura a la vez

---

## 🎯 El Problema Original

> "Si intento agruparlos en un array o vector, el envío me rebota porque no sabe como procesarlo"

**Solución:** Ahora hay un endpoint nuevo que acepta **una lectura a la vez** sin necesidad de arrays.

---

## ✅ Nueva URL (Recomendada para ti)

```
POST https://atabey-backend-k7kh.onrender.com/readings/single
```

**SIN autenticación, igual que antes.**

---

## 📋 Estructura JSON Simplificada

En lugar de:
```json
{
  "device_id": "ESP32-01",
  "buffer_id": "BUFFER-001",
  "readings": [
    {
      "device_id": "ESP32-01",
      "sensor_id": "TEMP-01",
      "timestamp": "2026-11-06T20:15:00Z",
      "value": 28.4,
      "unit": "C",
      "sequence": 1
    }
  ]
}
```

Ahora simplemente:
```json
{
  "device_id": "ESP32-01",
  "sensor_id": "TEMP-01",
  "timestamp": "2026-11-06T20:15:00Z",
  "value": 28.4,
  "unit": "C",
  "sequence": 1
}
```

**¡Mucho más simple!**

---

## 💻 Código Arduino (ESP32) - Actualizado

```cpp
#include <WiFi.h>
#include <HTTPClient.h>

const char* ssid = "tu-red-wifi";
const char* password = "tu-contraseña";
const char* backendUrl = "https://atabey-backend-k7kh.onrender.com/readings/single";

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi conectado");
}

void loop() {
  // Leer sensor de temperatura
  float tempValue = readTemperature();
  
  if (WiFi.connected()) {
    HTTPClient http;
    http.begin(backendUrl);
    http.addHeader("Content-Type", "application/json");
    
    // JSON simple - UNA lectura sin agrupar
    String payload = "{";
    payload += "\"device_id\":\"ESP32-01\",";
    payload += "\"sensor_id\":\"TEMP-01\",";
    payload += "\"timestamp\":\"" + getISO8601Timestamp() + "\",";
    payload += "\"value\":" + String(tempValue, 2) + ",";
    payload += "\"unit\":\"C\",";
    payload += "\"sequence\":1";
    payload += "}";
    
    int httpResponseCode = http.POST(payload);
    
    if (httpResponseCode == 200) {
      Serial.println("✓ Lectura enviada");
    } else {
      Serial.print("✗ Error HTTP: ");
      Serial.println(httpResponseCode);
    }
    
    http.end();
  }
  
  delay(5000); // Enviar cada 5 segundos
}

float readTemperature() {
  // Tu código aquí
  return 25.5;
}

String getISO8601Timestamp() {
  // Tu código aquí
  return "2026-11-06T20:15:00Z";
}
```

---

## 🧪 Test con curl

```bash
curl -X POST https://atabey-backend-k7kh.onrender.com/readings/single \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "ESP32-01",
    "sensor_id": "TEMP-01",
    "timestamp": "2026-11-06T20:15:00Z",
    "value": 28.4,
    "unit": "C",
    "sequence": 1
  }'
```

**Respuesta esperada (HTTP 200):**
```json
{
  "type": "ack",
  "device_id": "ESP32-01",
  "buffer_id": "SINGLE-a1b2c3d4",
  "received_at": "2026-11-07T01:45:00Z",
  "accepted": 1,
  "rejected": 0,
  "duplicates": 0,
  "items": [
    {
      "sensor_id": "TEMP-01",
      "sequence": 1,
      "status": "stored",
      "received_at": "2026-11-07T01:45:00Z",
      "db_id": 123,
      "error": null
    }
  ]
}
```

---

## 📊 Comparación: Antigua vs Nueva Ruta

| Aspecto | `/readings/batch` | `/readings/single` |
|---------|------|------|
| **Estructura** | Buffer + array | Lectura simple |
| **Complejidad** | Más código | Mucho menos |
| **Buffer_id** | Requerido | Generado automático |
| **Readings array** | Sí | No |
| **Ideal para** | Lotes múltiples | Una a la vez |
| **Vantroi** | ❌ No puede | ✅ SÍ PUEDE |

---

## 🚀 Instrucciones

1. **Sigue usando:** `https://atabey-backend-k7kh.onrender.com/readings/single`
2. **JSON:** Sin `buffer_id`, sin array `readings`
3. **Estructura:** Solo los 6 campos de la lectura
4. **Envía cada lectura** cuando esté lista (uno a uno, perfecto así)

---

## ✅ Ventajas

- ✅ Mucho código más simple en el ESP32
- ✅ Menos RAM necesaria (sin arrays)
- ✅ Puedes enviar valores conforme se miden
- ✅ El servidor agrupa todo automáticamente
- ✅ No pierdes eficiencia (el servidor maneja la optimización)

---

## 📌 El Servidor Ahora Hace Esto Automáticamente

Cuando recibes una lectura individual en `/readings/single`:

1. La recibe como JSON simple
2. La agrupa internamente en un buffer
3. La procesa igual que las lecturas en batch
4. Te devuelve el ACK completo

**Tú solo envías valores sueltos — el servidor se encarga del resto.**

---

## 🆘 Si Necesitas Ayuda

Documenta en los logs:
- Timestamp del envío
- Valor e unidad
- HTTP response code
- Contenido del ACK recibido

Y comparte en el chat de Whatsapp.

---

¡Listo! 🎉 La conex está optimizada para tu hardware.

