# Actualización: Error #404 → Ahora RESUELTO ✅

**Fecha:** 6 Nov 2026, después del error #404  
**Problema:** El endpoint `/api/ingest` no existía (error 404)  
**Solución:** Acabo de crear el endpoint abierto sin requerer autenticación

---

## 🔧 Qué cambió

- **Nuevo endpoint:** `POST https://atabey-backend-k7kh.onrender.com/api/ingest`
- **Sin autenticación:** No necesitas token, no necesitas login
- **Mismo formato JSON:** Igual estructura que indicamos antes

---

## ✅ Próximo paso: Prueba rápida

Usa **exactamente** este comando curl para verificar que funciona:

```bash
curl -X POST https://atabey-backend-k7kh.onrender.com/api/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "ESP32-01",
    "sensor_id": "TEMP-01",
    "timestamp": "2026-11-06T20:15:00Z",
    "value": 25.5,
    "unit": "C",
    "sequence": 1,
    "buffer_id": "BUFFER-001"
  }'
```

**Respuesta esperada (HTTP 200):**
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

## ⚠️ IMPORTANTE: Estructura del JSON

El endpoint espera un **BUFFER** (lote), no un solo dato. Esto significa:

```json
{
  "device_id": "ESP32-01",        ← ID del dispositivo
  "buffer_id": "BUFFER-001",      ← ID único del lote (ej: timestamp o contador)
  "readings": [                    ← ARRAY de lecturas
    {
      "sensor_id": "TEMP-01",
      "timestamp": "2026-11-06T20:15:00Z",
      "value": 25.5,
      "unit": "C",
      "sequence": 1
    }
  ]
}
```

**Nota:** Si envías una sola lectura, sigue siendo un buffer con `readings: [...]` de 1 elemento.

---

## 📝 Ejemplo de Arduino (actualizado)

```cpp
void sendDataToBackend(float tempValue) {
  if (!WiFi.connected()) return;
  
  HTTPClient http;
  http.begin("https://atabey-backend-k7kh.onrender.com/api/ingest");
  http.addHeader("Content-Type", "application/json");
  
  String buffer_id = "BUFFER-" + String(millis());
  
  String payload = R"({
    "device_id": "ESP32-01",
    "buffer_id": ")" + buffer_id + R"(",
    "readings": [
      {
        "sensor_id": "TEMP-01",
        "timestamp": "2026-11-06T20:15:00Z",
        "value": )" + String(tempValue, 2) + R"(,
        "unit": "C",
        "sequence": 1
      }
    ]
  })";
  
  int httpCode = http.POST(payload);
  
  if (httpCode == 200) {
    Serial.println("✓ Dato enviado exitosamente");
  } else {
    Serial.print("✗ Error HTTP: ");
    Serial.println(httpCode);
    Serial.println(http.getString());
  }
  
  http.end();
}
```

---

## 🚀 Status

- ✅ Backend redeployado con nuevo endpoint
- ✅ Frontend actualizada con URL correcta
- ⏳ Render desplegando cambios (ETA ~30-60 seg)
- ➡️ **Vantroi:** Intenta el curl arriba cuando Render termine el deploy

¡Avísame cuando envíes datos y vemos los resultados en el dashboard!

