# Guía: Enviar datos desde ESP32 a Producción (Render)

**Status:** ✅ Backend y Frontend desplegados en Render  
**Fecha:** 6 Nov 2026  
**Dirigido a:** Vantroi (ubicación remota)

---

## 🎯 Resumen: Dónde enviar los datos

Tu ESP32 debe enviar datos **aquí**:

```
POST https://atabey-backend-k7kh.onrender.com/api/ingest
```

**NO** a la frontend (ese era el error #307 que recibiste).

---

## 📋 Endpoint de Ingesta

### URL
```
https://atabey-backend-k7kh.onrender.com/api/ingest
```

### Método
```
POST
```

### Headers
```
Content-Type: application/json
```

### Body (JSON)
Cada lectura de sensor sigue esta estructura exacta:

```json
{
  "device_id": "ESP32-01",
  "sensor_id": "TEMP-01",
  "timestamp": "2026-11-06T20:15:00Z",
  "value": 28.4,
  "unit": "C",
  "sequence": 1542
}
```

**Campos:**
- `device_id`: Identificador del ESP32 (ej. `ESP32-01`, `ESP32-02`)
- `sensor_id`: Identificador del sensor (ej. `TEMP-01`, `HUMIDITY-01`, `PULSE-01`)
- `timestamp`: Marca de tiempo en ISO 8601 UTC
- `value`: Valor numérico de la lectura
- `unit`: Unidad de medida (ej. `C`, `%`, `bpm`, `ppm`)
- `sequence`: Contador incremental por sensor (para detectar lecturas perdidas)

---

## 💻 Código Arduino (ESP32) — Ejemplo

```cpp
#include <WiFi.h>
#include <HTTPClient.h>

const char* ssid = "tu-red-wifi";
const char* password = "tu-contraseña";
const char* backendUrl = "https://atabey-backend-k7kh.onrender.com/api/ingest";

int sensorSequence = 0;

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
  // Leer sensor de temperatura (ejemplo)
  float tempValue = readTemperature();
  
  if (WiFi.connected()) {
    HTTPClient http;
    http.begin(backendUrl);
    http.addHeader("Content-Type", "application/json");
    
    // Construir JSON
    String payload = "{\"device_id\":\"ESP32-01\",\"sensor_id\":\"TEMP-01\",\"timestamp\":\"";
    payload += getISO8601Timestamp();
    payload += "\",\"value\":";
    payload += String(tempValue, 2);
    payload += ",\"unit\":\"C\",\"sequence\":";
    payload += String(sensorSequence++);
    payload += "}";
    
    int httpResponseCode = http.POST(payload);
    
    if (httpResponseCode == 200) {
      Serial.println("✓ Dato enviado");
    } else {
      Serial.print("✗ Error HTTP: ");
      Serial.println(httpResponseCode);
    }
    
    http.end();
  }
  
  delay(5000); // Enviar cada 5 segundos
}

float readTemperature() {
  // Tu código de lectura de sensor aquí
  return 25.5; // Placeholder
}

String getISO8601Timestamp() {
  // Tu código para obtener timestamp ISO 8601 aquí
  // Ej: "2026-11-06T20:15:00Z"
  return "2026-11-06T20:15:00Z"; // Placeholder
}
```

---

## 🧪 Probar sin hardware (curl)

Si quieres probar el endpoint sin ESP32:

```bash
curl -X POST https://atabey-backend-k7kh.onrender.com/api/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "ESP32-01",
    "sensor_id": "TEMP-01",
    "timestamp": "2026-11-06T20:15:00Z",
    "value": 28.4,
    "unit": "C",
    "sequence": 1542
  }'
```

**Respuesta esperada (HTTP 200):**
```json
{
  "status": "ok",
  "message": "Reading ingested",
  "reading_id": 12345
}
```

---

## 📊 Ver los datos en vivo

Después de enviar datos, aparecerán en el **dashboard en tiempo real**:

```
https://atabey-frontend.onrender.com
```

- No requiere login (modo desarrollo, acceso abierto)
- Los datos aparecen en las pestañas **"Tripulantes"** o **"Domo"** según el tipo de sensor
- Histórico visible en gráficos

---

## 🔗 URLs de Referencia

| Componente | URL |
|-----------|-----|
| Backend API | `https://atabey-backend-k7kh.onrender.com` |
| API Docs (Swagger) | `https://atabey-backend-k7kh.onrender.com/docs` |
| Frontend Dashboard | `https://atabey-frontend.onrender.com` |
| WebSocket (datos vivos) | `wss://atabey-backend-k7kh.onrender.com/ws` |

---

## ❓ Troubleshooting

### Error #307 (Redirect)
**Problema:** Estabas enviando a la frontend en lugar de la API.  
**Solución:** Usa `https://atabey-backend-k7kh.onrender.com/api/ingest` (este documento).

### Error 500 en backend
**Posible causa:** Formato JSON inválido o campos faltantes.  
**Solución:** Verifica que coincida exactamente con la estructura de arriba.

### Timeout de conexión
**Posible causa:** Render en cold start o sin conexión Internet.  
**Solución:** 
- Primer request tarda ~30s (cold start). Los siguientes son rápidos.
- Verifica que tu ESP32 tenga conexión WiFi.

### Los datos no aparecen en el dashboard
**Verificar:**
1. ¿El backend recibió el dato? Chequea `/api/readings` o `/api/readings/latest`
2. ¿El tipo de sensor está en el catálogo? Ver `/api/catalog/sensors`
3. ¿La frontend se refresco? (F5 en el navegador)

---

## 📞 Contacto

Si hay problemas:
1. Verifica el formato JSON (usa curl para testear)
2. Chequea los logs del backend: `https://atabey-backend-k7kh.onrender.com/docs` → Swagger interactivo
3. Comparte el error exacto (HTTP code, JSON response)

---

## 📌 Checklist antes de enviar datos

- [ ] WiFi en ESP32 está conectado
- [ ] URL correcta: `https://atabey-backend-k7kh.onrender.com/api/ingest`
- [ ] JSON válido (prueba con curl primero)
- [ ] `timestamp` en formato ISO 8601 UTC
- [ ] `sequence` incrementa por cada lectura
- [ ] Headers: `Content-Type: application/json`
- [ ] Esperar ~30s en primer request (cold start)
- [ ] Ver datos en dashboard: `https://atabey-frontend.onrender.com`

¡Listo!

