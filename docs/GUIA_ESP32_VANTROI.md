# 📡 Guía para ESP32 - Vantroi desde Casa

## Conexión a Sistema Atabey

Bienvenido Vantroi. Este documento te guía paso a paso para conectar tu ESP32 al sistema Atabey de telemetría y enviar datos de sensores del domo.

---

## 🎯 Lo Que Necesitas

1. **ESP32** con conexión WiFi
2. **MQTT Client**: PubSubClient.h (para Arduino IDE)
3. **JSON library**: ArduinoJson (para Arduino IDE)
4. **Sensores** (temperatura, humedad, etc.)
5. **Estos datos** de configuración (más abajo)

---

## 🌐 Configuración de Red

### Server MQTT (Backend de Atabey)

```
Host:     tu-ip-publica-o-dominio  (preguntale a tu-usuario si no la sabes)
Puerto:   1883 (MQTT sin encriptación, desarrollo)
Usuario:  (opcional, sin autenticación en desarrollo)
Password: (opcional, sin autenticación en desarrollo)
```

**Para desarrollo local:**
Si estás en la misma red que el backend, usa la **IP local del servidor**:
```
Host: 192.168.X.X  (ejemplo: 192.168.1.100)
o
Host: localhost (si el ESP32 esta en la misma máquina)
```

### WiFi
```
SSID:     tu-red-wifi
Password: tu-contraseña-wifi
```

---

## 📋 Lista de Sensores - Variables y Nombres

Tu ESP32 debe leer sensores y enviar los datos con estos **IDs exactos**. 

### 🌱 Sensores del Domo (si tienes)

| sensor_id | variable | nombre | unit | rango |
|-----------|----------|--------|------|-------|
| TEMP-01 | temperatura_aire | Temperatura del Aire | °C | 15.0 - 35.0 |
| HUM-01 | humedad_aire | Humedad del Aire | % | 40.0 - 85.0 |
| CO2-01 | concentracion_co2 | Concentración CO2 | ppm | 400.0 - 1200.0 |
| LUX-01 | luz_ambiental | Iluminación | lux | 100.0 - 3000.0 |
| SOIL-HUM-01 | humedad_suelo_1 | Humedad Suelo S1 | % | 20.0 - 70.0 |
| SOIL-HUM-02 | humedad_suelo_2 | Humedad Suelo S2 | % | 20.0 - 70.0 |
| SOIL-HUM-03 | humedad_suelo_3 | Humedad Suelo S3 | % | 20.0 - 70.0 |
| SOIL-TEMP-01 | temperatura_suelo_1 | Temperatura Suelo S1 | °C | 15.0 - 30.0 |
| SOIL-TEMP-02 | temperatura_suelo_2 | Temperatura Suelo S2 | °C | 15.0 - 30.0 |
| SOIL-TEMP-03 | temperatura_suelo_3 | Temperatura Suelo S3 | °C | 15.0 - 30.0 |

### 👤 Sensores del Tripulante EVA (si tienes)

| sensor_id | variable | nombre | unit | rango |
|-----------|----------|--------|------|-------|
| HR-01 | pulso_cardiaco | Pulso Cardiaco | bpm | 55.0 - 140.0 |
| SPO2-01 | saturacion_oxigeno | Saturación O2 | % | 92.0 - 100.0 |
| BTEMP-01 | temperatura_corporal | Temperatura Corporal | °C | 34.5 - 37.5 |
| EVA-TEMP-01 | temperatura_traje | Temperatura del Traje | °C | 15.0 - 35.0 |
| EVA-HUM-01 | humedad_traje | Humedad del Traje | % | 30.0 - 70.0 |
| EVA-PRESS-01 | presion_traje | Presión del Traje | hPa | 950.0 - 1030.0 |
| ACC-X-01 | aceleracion_x | Aceleración X | m/s² | -3.0 - 3.0 |
| ACC-Y-01 | aceleracion_y | Aceleración Y | m/s² | -3.0 - 3.0 |
| ACC-Z-01 | aceleracion_z | Aceleración Z | m/s² | -3.0 - 3.0 |
| ACTIVITY-01 | actividad | Estado Actividad | código | 0 - 3 |

**Notas:**
- ✅ BIOMÉTRICOS (HR-01, SPO2-01, BTEMP-01) = datos del tripulante (restringidos a rol administrador)
- ✅ EVA-* = datos del traje de soporte de vida (operacionales)
- ✅ ACTIVITY-01 = 0:Still, 1:Walking, 2:Running, 3:Tilting

---

## 📝 Contrato de Datos - Formato JSON

Tu ESP32 DEBE enviar datos en este formato exacto:

### 1. **Lectura Individual** (SensorReading)
```json
{
  "device_id": "ESP32-01",
  "sensor_id": "TEMP-01",
  "timestamp": "2026-11-01T14:30:00Z",
  "value": 28.4,
  "unit": "C",
  "sequence": 1
}
```

### 2. **Buffer** (Lote de Lecturas)
Tu ESP32 acumula lecturas y las envía de una sola vez:

```json
{
  "device_id": "ESP32-01",
  "buffer_id": "ESP32-01_20261101_143000_abc123",
  "sent_at": "2026-11-01T14:30:00Z",
  "readings": [
    {
      "device_id": "ESP32-01",
      "sensor_id": "TEMP-01",
      "timestamp": "2026-11-01T14:30:00Z",
      "value": 28.4,
      "unit": "C",
      "sequence": 1
    },
    {
      "device_id": "ESP32-01",
      "sensor_id": "HUM-01",
      "timestamp": "2026-11-01T14:30:00Z",
      "value": 65.2,
      "unit": "%",
      "sequence": 1
    }
  ]
}
```

**Campos obligatorios:**
- `device_id`: Identificador único de tu ESP32 (ej: "ESP32-01", "ESP32-VANTROI", etc.)
- `buffer_id`: ID único de este envío (recomendado: `device_id_timestamp_random`)
- `sent_at`: Hora UTC cuando el ESP32 envió (ISO-8601 format)
- `readings`: Array con al menos 1 lectura
  - `device_id`: Mismo que el buffer
  - `sensor_id`: ID exacto del sensor (de la tabla de arriba)
  - `timestamp`: Hora UTC cuando el sensor midió (ISO-8601)
  - `value`: Número (float o int)
  - `unit`: Unidad (C, %, ppm, lux, etc.) - debe ser exacta
  - `sequence`: Contador incremental por sensor (ej: sensor TEMP-01 cuenta 1, 2, 3...)

---

## 🔄 Flujo de Datos (Pipeline)

```
1. ESP32 lee sensores cada 5 segundos
   └─ temperatura_aire = 28.4°C
   └─ humedad_aire = 65.2%
   └─ ...

2. ESP32 acumula en buffer local (cada 30 segundos / 6 lecturas)

3. ESP32 se conecta a WiFi → MQTT
   └─ Publica en: atabey/ESP32-01/buffer
   └─ JSON con todas las lecturas

4. Backend recibe, valida, guarda en PostgreSQL

5. Backend publica ACK (confirmación):
   └─ Topic: atabey/ack/ESP32-01
   └─ JSON: {type: "ack", accepted: 6, rejected: 0, ...}

6. ESP32 ve el ACK → sabe que llegó correctamente

7. Dashboard (http://localhost:5173) recibe datos por WebSocket
   └─ Ve gráficos en tiempo real
   └─ Alertas si sensores salen de rango
```

---

## 💾 Código Arduino Básico

```cpp
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <time.h>

// ═══════════════════════════════════════════════════════════════════════════
// Configuración
// ═══════════════════════════════════════════════════════════════════════════

const char* WIFI_SSID = "TU_RED_WIFI";
const char* WIFI_PASSWORD = "TU_CONTRASEÑA";

const char* MQTT_SERVER = "192.168.1.100";  // IP del servidor Atabey
const int MQTT_PORT = 1883;
const char* DEVICE_ID = "ESP32-01";        // Tu ID único

// ═══════════════════════════════════════════════════════════════════════════
// Clientes
// ═══════════════════════════════════════════════════════════════════════════

WiFiClient espClient;
PubSubClient client(espClient);

// ═══════════════════════════════════════════════════════════════════════════
// Variables Globales
// ═══════════════════════════════════════════════════════════════════════════

unsigned long lastReadTime = 0;
unsigned long readInterval = 5000;  // Leer sensores cada 5 segundos

unsigned long lastBufferTime = 0;
unsigned long bufferInterval = 30000;  // Enviar buffer cada 30 segundos

JsonArray readingsBuffer;
int bufferCount = 0;
int sequenceTemp = 0;  // Contador incremental por sensor
int sequenceHum = 0;

// ═══════════════════════════════════════════════════════════════════════════
// Setup
// ═══════════════════════════════════════════════════════════════════════════

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n╔═══════════════════════════════════════╗");
  Serial.println("║  Misión Atabey - ESP32 Node          ║");
  Serial.println("╚═══════════════════════════════════════╝\n");
  
  // Conectar a WiFi
  connectToWiFi();
  
  // Configurar MQTT
  client.setServer(MQTT_SERVER, MQTT_PORT);
  client.setCallback(onMessageReceived);
  
  // Sincronizar hora (opcional pero recomendado)
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.println("Sincronizando hora...");
  time_t now = time(nullptr);
  while (now < 24 * 3600 * 2) {
    delay(500);
    now = time(nullptr);
  }
  Serial.print("Hora sincronizada: ");
  Serial.println(ctime(&now));
  
  Serial.println("\n✓ Setup completado\n");
}

// ═══════════════════════════════════════════════════════════════════════════
// Loop Principal
// ═══════════════════════════════════════════════════════════════════════════

void loop() {
  // Mantener conexión MQTT
  if (!client.connected()) {
    connectToMQTT();
  }
  client.loop();
  
  // Leer sensores cada 5 segundos
  if (millis() - lastReadTime >= readInterval) {
    lastReadTime = millis();
    readSensorsAndAddToBuffer();
  }
  
  // Enviar buffer cada 30 segundos
  if (millis() - lastBufferTime >= bufferInterval) {
    lastBufferTime = millis();
    sendBuffer();
  }
  
  delay(100);  // CPU brake
}

// ═══════════════════════════════════════════════════════════════════════════
// WiFi
// ═══════════════════════════════════════════════════════════════════════════

void connectToWiFi() {
  Serial.print("Conectando a WiFi: ");
  Serial.println(WIFI_SSID);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✓ WiFi conectado");
    Serial.print("  IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n✗ Fallo de WiFi");
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// MQTT
// ═══════════════════════════════════════════════════════════════════════════

void connectToMQTT() {
  Serial.print("Conectando a MQTT: ");
  Serial.print(MQTT_SERVER);
  Serial.print(":");
  Serial.println(MQTT_PORT);
  
  String clientId = String(DEVICE_ID) + "_" + String(random(0xffff), HEX);
  
  if (client.connect(clientId.c_str())) {
    Serial.println("✓ MQTT conectado");
    
    // Suscribirse a ACKs
    String ackTopic = "atabey/ack/" + String(DEVICE_ID);
    client.subscribe(ackTopic.c_str());
    Serial.print("  Escuchando: ");
    Serial.println(ackTopic);
  } else {
    Serial.print("✗ Error MQTT: ");
    Serial.println(client.state());
    delay(5000);
  }
}

void onMessageReceived(char* topic, byte* payload, unsigned int length) {
  Serial.print("📥 Mensaje recibido en: ");
  Serial.println(topic);
  
  // Mostrar JSON
  Serial.print("   Payload: ");
  for (int i = 0; i < length; i++) {
    Serial.print((char)payload[i]);
  }
  Serial.println();
  
  // Aquí puedes procesar el ACK si necesitas
}

// ═══════════════════════════════════════════════════════════════════════════
// Sensores
// ═══════════════════════════════════════════════════════════════════════════

void readSensorsAndAddToBuffer() {
  // NOTA: Aquí van tus sensores reales
  // Este es un ejemplo de lectura simulada
  
  float tempValue = 25.0 + (random(-20, 20) / 10.0);  // Temperatura 24-26°C
  float humValue = 60.0 + (random(-20, 20) / 10.0);   // Humedad 59-61%
  
  Serial.print("📊 Lectura #");
  Serial.print(bufferCount + 1);
  Serial.print(": TEMP=");
  Serial.print(tempValue);
  Serial.print("°C, HUM=");
  Serial.print(humValue);
  Serial.println("%");
  
  // Agregar lectura 1: Temperatura
  addReadingToBuffer("TEMP-01", tempValue, "C", sequenceTemp++);
  
  // Agregar lectura 2: Humedad
  addReadingToBuffer("HUM-01", humValue, "%", sequenceHum++);
  
  bufferCount++;
}

void addReadingToBuffer(const char* sensorId, float value, const char* unit, int sequence) {
  // Crear documento JSON para esta lectura
  StaticJsonDocument<256> doc;
  
  time_t now = time(nullptr);
  struct tm* timeinfo = gmtime(&now);
  char timestamp[32];
  strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", timeinfo);
  
  doc["device_id"] = DEVICE_ID;
  doc["sensor_id"] = sensorId;
  doc["timestamp"] = timestamp;
  doc["value"] = value;
  doc["unit"] = unit;
  doc["sequence"] = sequence;
  
  // Serializar a String para guardar en buffer
  String jsonStr;
  serializeJson(doc, jsonStr);
  
  // En una app real, guardarías esto en un array o base de datos local
  // Por ahora solo lo enviamos directamente
}

// ═══════════════════════════════════════════════════════════════════════════
// Buffer y Envío
// ═══════════════════════════════════════════════════════════════════════════

void sendBuffer() {
  if (bufferCount == 0) {
    Serial.println("⚠ Buffer vacío, nada que enviar");
    return;
  }
  
  // Crear JSON del buffer
  StaticJsonDocument<2048> bufferDoc;
  
  time_t now = time(nullptr);
  struct tm* timeinfo = gmtime(&now);
  char timestamp[32];
  strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", timeinfo);
  
  bufferDoc["device_id"] = DEVICE_ID;
  
  // buffer_id único
  String bufferId = String(DEVICE_ID) + "_" + String(timestamp) + "_" + String(random(0xffff), HEX);
  bufferDoc["buffer_id"] = bufferId;
  bufferDoc["sent_at"] = timestamp;
  
  // Agregar lecturas (simuladas para este ejemplo)
  JsonArray readings = bufferDoc.createNestedArray("readings");
  
  for (int i = 0; i < bufferCount; i++) {
    JsonObject reading = readings.createNestedObject();
    reading["device_id"] = DEVICE_ID;
    reading["sensor_id"] = (i % 2 == 0) ? "TEMP-01" : "HUM-01";
    reading["timestamp"] = timestamp;
    reading["value"] = (i % 2 == 0) ? 25.0 + (random(-10, 10) / 10.0) : 60.0 + (random(-10, 10) / 10.0);
    reading["unit"] = (i % 2 == 0) ? "C" : "%";
    reading["sequence"] = i + 1;
  }
  
  // Serializar
  String payload;
  serializeJson(bufferDoc, payload);
  
  // Publicar en MQTT
  String topic = "atabey/" + String(DEVICE_ID) + "/buffer";
  
  Serial.print("📤 Enviando buffer ");
  Serial.print(bufferCount);
  Serial.print(" lecturas a: ");
  Serial.println(topic);
  Serial.print("   Tamaño: ");
  Serial.print(payload.length());
  Serial.println(" bytes");
  
  if (client.publish(topic.c_str(), payload.c_str())) {
    Serial.println("✓ Buffer enviado exitosamente");
  } else {
    Serial.println("✗ Error al enviar buffer");
  }
  
  // Reset
  bufferCount = 0;
}
```

---

## 🔌 Configurar Sensores Reales

En la función `readSensorsAndAddToBuffer()`, reemplaza la lectura simulada con tus sensores:

### Ejemplo: DHT22 (Temperatura + Humedad)
```cpp
#include <DHT.h>

#define DHTPIN 4
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);

void readSensorsAndAddToBuffer() {
  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature();
  
  if (isnan(humidity) || isnan(temperature)) {
    Serial.println("✗ Error leyendo DHT22");
    return;
  }
  
  addReadingToBuffer("TEMP-01", temperature, "C", sequenceTemp++);
  addReadingToBuffer("HUM-01", humidity, "%", sequenceHum++);
}
```

### Ejemplo: Sensor de Luz (TSL2591)
```cpp
#include <Adafruit_TSL2591.h>

Adafruit_TSL2591 tsl = Adafruit_TSL2591(2561);

void readSensorsAndAddToBuffer() {
  uint16_t infrared = tsl.getLuminosity(TSL2591_INFRARED);
  uint16_t fullSpectrum = tsl.getLuminosity(TSL2591_FULLSPECTRUM);
  uint16_t visible = fullSpectrum - infrared;
  uint32_t lux = tsl.calculateLux(fullSpectrum, infrared);
  
  addReadingToBuffer("LUX-01", (float)lux, "lux", sequenceLux++);
}
```

---

## 🧪 Pruebas

### 1. Monitor Serial
```
Abre Arduino IDE → Herramientas → Monitor Serie (115200 baud)

Deberías ver:
  ╔═══════════════════════════════════════╗
  ║  Misión Atabey - ESP32 Node          ║
  ╚═══════════════════════════════════════╝

  Conectando a WiFi: MI_ROUTER
  ✓ WiFi conectado
    IP: 192.168.1.50

  Conectando a MQTT: 192.168.1.100:1883
  ✓ MQTT conectado
    Escuchando: atabey/ack/ESP32-01

  📊 Lectura #1: TEMP=25.3°C, HUM=60.2%
  📤 Enviando buffer 6 lecturas a: atabey/ESP32-01/buffer
  ✓ Buffer enviado exitosamente
```

### 2. Ver Datos en Dashboard
- Abre http://localhost:5173
- Ve a Vista "Domo" o "Tripulante"
- Deberías ver tus sensores en tiempo real

### 3. Verificar Datos en Backend
```bash
# Terminal en la máquina del servidor
curl http://localhost:8000/readings/latest?sensor_id=TEMP-01

# Debería devolver:
{
  "sensor_id": "TEMP-01",
  "device_id": "ESP32-01",
  "value": 25.3,
  "unit": "C",
  "timestamp": "2026-11-01T14:30:00Z",
  "sequence": 123
}
```

### 4. Ver en MQTT (opcional)
```bash
# Terminal en la máquina del servidor
mosquitto_sub -h localhost -p 1883 -t "atabey/#"

# Deberías ver:
atabey/ESP32-01/buffer {"device_id":"ESP32-01","buffer_id":"ESP32-01_...",
atabey/ack/ESP32-01 {"type":"ack","device_id":"ESP32-01","accepted":6,...}
```

---

## 🐛 Troubleshooting

| Problema | Solución |
|----------|----------|
| **No conecta WiFi** | Verifica SSID y password en el código |
| **MQTT connection refused** | Verifica IP del servidor, asegúrate que MQTT esté corriendo |
| **Buffer no se envía** | Revisa que el tiempo se sincronizó (NTP) |
| **Dashboard no muestra datos** | Verifica que sensor_id sea exacto (TEMP-01, no temp-01) |
| **Error JSON** | Usa un validador: https://jsonlint.com/ |
| **ACK nunca llega** | Verifica que ESP32 esté suscrito a `atabey/ack/ESP32-01` |

---

## 📞 Contacto

Si tienes problemas o preguntas:
1. Revisa los logs del Arduino Monitor (Serial)
2. Verifica los logs del backend:
   ```bash
   # Terminal en servidor
   tail -f backend/server.log
   ```
3. Revisa este documento
4. Contacta a tu-usuario

---

## ✅ Checklist Antes de Enviar

- [ ] ESP32 compiló sin errores
- [ ] WiFi conecta exitosamente
- [ ] MQTT conecta y suscribe a ACK
- [ ] Sensores leen valores razonables
- [ ] Buffer se envía cada 30 segundos
- [ ] Ves "Buffer enviado exitosamente" en Serial
- [ ] Dashboard muestra datos en tiempo real
- [ ] Endpoint `/readings/latest` devuelve tus datos

**¡Listo! Tu ESP32 está contribuyendo a Misión Atabey 🚀**
