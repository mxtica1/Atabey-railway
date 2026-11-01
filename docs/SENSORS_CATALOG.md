# Catálogo de variables de sensores — Misión Atabey 1

**Fuente de verdad:** `backend/catalog.py` · **Expuesto en:** `GET /sensors/catalog`

Este documento lista **todas** las variables que el ESP32/firmware puede enviar.
Es la referencia para armar buffers de datos válidos.

---

## 1. Contrato de lectura (no cambia — AGENTS.md)

Cada lectura dentro de un buffer sigue esta estructura **exacta**:

```json
{
  "device_id": "ESP32-01",
  "sensor_id": "TEMP-01",
  "timestamp": "2026-09-24T20:15:00Z",
  "value": 28.4,
  "unit": "C",
  "sequence": 1542
}
```

| Campo | Tipo | Regla |
|---|---|---|
| `device_id` | string | `ESP32-01` (domo) o `EVA-01` (tripulante) |
| `sensor_id` | string | debe existir en el catálogo |
| `timestamp` | ISO-8601 UTC | **momento en que el sensor midió** (no cuando se guardó) |
| `value` | number | el valor medido |
| `unit` | string | la unidad del catálogo (ver tabla) |
| `sequence` | int | contador incremental **por sensor**, para detectar lecturas perdidas |

---

## 2. Variables disponibles — 23 sensores

### 2.1 ESP32-01 · Domo (13 sensores)

| `sensor_id` | Variable | Nombre | Unidad | Grupo | Hardware | Rango | Umbral |
|---|---|---|---|---|---|---|---|
| `TEMP-01` | `temperatura_aire` | Temperatura del Aire | `C` | domo_ambiental | DS18B20 / TMP117 | 15–35 | 15–35 |
| `HUM-01` | `humedad_aire` | Humedad del Aire | `%` | domo_ambiental | DHT22 / SHT31 | 40–85 | 40–85 |
| `CO2-01` | `concentracion_co2` | Concentración de Gas (CO₂) | `ppm` | domo_ambiental | MH-Z19 | 400–1200 | 400–1200 |
| `LUX-01` | `luz_ambiental` | Iluminación (lux) | `lux` | domo_ambiental | TSL2591 | 100–3000 | 100–3000 |
| `SOIL-HUM-01` | `humedad_suelo_1` | Humedad del Suelo S1 | `%` | domo_suelo | STEMMA Soil | 20–70 | 20–70 |
| `SOIL-HUM-02` | `humedad_suelo_2` | Humedad del Suelo S2 | `%` | domo_suelo | STEMMA Soil | 20–70 | 20–70 |
| `SOIL-HUM-03` | `humedad_suelo_3` | Humedad del Suelo S3 | `%` | domo_suelo | STEMMA Soil | 20–70 | 20–70 |
| `SOIL-TEMP-01` | `temperatura_suelo_1` | Temperatura del Suelo S1 | `C` | domo_suelo | STEMMA Soil | 15–30 | 15–30 |
| `SOIL-TEMP-02` | `temperatura_suelo_2` | Temperatura del Suelo S2 | `C` | domo_suelo | STEMMA Soil | 15–30 | 15–30 |
| `SOIL-TEMP-03` | `temperatura_suelo_3` | Temperatura del Suelo S3 | `C` | domo_suelo | STEMMA Soil | 15–30 | 15–30 |
| `NPK-N-01` | `nitrogeno_suelo` | Nitrógeno (N) | `mg/kg` | domo_suelo | ⚠️ simulado | 50–300 | 50–300 |
| `NPK-P-01` | `fosforo_suelo` | Fósforo (P) | `mg/kg` | domo_suelo | ⚠️ simulado | 20–150 | 20–150 |
| `NPK-K-01` | `potasio_suelo` | Potasio (K) | `mg/kg` | domo_suelo | ⚠️ simulado | 100–400 | 100–400 |

### 2.2 EVA-01 · Mochila del tripulante (10 sensores)

| `sensor_id` | Variable | Nombre | Unidad | Grupo | Hardware | Rango | Umbral | Bio |
|---|---|---|---|---|---|---|---|---|
| `HR-01` | `pulso_cardiaco` | Pulso Cardíaco | `bpm` | bio | MAX30102 (confirmar) | 55–140 | 55–140 | 🔒 |
| `SPO2-01` | `saturacion_oxigeno` | Saturación de Oxígeno (SpO₂) | `%` | bio | MAX30102 (confirmar) | 92–100 | 92–100 | 🔒 |
| `BTEMP-01` | `temperatura_corporal` | Temperatura Corporal | `C` | bio | sensor corporal (confirmar) | 34.5–37.5 | 34.5–37.5 | 🔒 |
| `EVA-TEMP-01` | `temperatura_traje` | Temperatura del Traje | `C` | eva | DS18B20 / TMP117 | 15–35 | 15–35 | — |
| `EVA-HUM-01` | `humedad_traje` | Humedad del Traje | `%` | eva | DHT22 / SHT31 | 30–70 | 30–70 | — |
| `EVA-PRESS-01` | `presion_traje` | Presión del Traje | `hPa` | eva | BMP280 / MS5611 | 950–1030 | 950–1030 | — |
| `ACC-X-01` | `aceleracion_x` | Aceleración X | `m/s²` | imu | BNO055 | −3–3 | — | — |
| `ACC-Y-01` | `aceleracion_y` | Aceleración Y | `m/s²` | imu | BNO055 | −3–3 | — | — |
| `ACC-Z-01` | `aceleracion_z` | Aceleración Z | `m/s²` | imu | BNO055 | −3–3 | — | — |
| `ACTIVITY-01` | `actividad` | Estado de Actividad | `código` | imu | BNO055 | 0–3 | — | — |

`ACTIVITY-01` es categórico: `0=Still`, `1=Walking`, `2=Running`, `3=Tilting`.

🔒 = biométrico → acceso restringido por rol (Administrador / Control de Misión).

### 2.3 Notas sobre el hardware

- **NPK-\*** no tiene sensor físico documentado — se simula. Confirmar antes de usar en vuelo.
- **SOIL-HUM-\* / SOIL-TEMP-\*** salen del mismo STEMMA Soil Sensor (una lectura física, dos magnitudes).
- **LUX-01** es el TSL2591 (lux, visible + infrarrojo). **No** es un índice UV.
- **ECG crudo (AD8232)** queda fuera del alcance actual.
- **BNO055** solo aporta aceleración lineal + actividad en este corte.

---

## 3. Resumen rápido (copiar/pegar)

```
TEMP-01,HUM-01,CO2-01,LUX-01,
SOIL-HUM-01,SOIL-HUM-02,SOIL-HUM-03,
SOIL-TEMP-01,SOIL-TEMP-02,SOIL-TEMP-03,
NPK-N-01,NPK-P-01,NPK-K-01,
HR-01,SPO2-01,BTEMP-01,
EVA-TEMP-01,EVA-HUM-01,EVA-PRESS-01,
ACC-X-01,ACC-Y-01,ACC-Z-01,ACTIVITY-01
```

**Variables (para el firmware):**

```json
{
  "TEMP-01":      { "variable": "temperatura_aire",      "unit": "C",      "device_id": "ESP32-01" },
  "HUM-01":       { "variable": "humedad_aire",          "unit": "%",      "device_id": "ESP32-01" },
  "CO2-01":       { "variable": "concentracion_co2",     "unit": "ppm",    "device_id": "ESP32-01" },
  "LUX-01":       { "variable": "luz_ambiental",         "unit": "lux",    "device_id": "ESP32-01" },
  "SOIL-HUM-01":  { "variable": "humedad_suelo_1",       "unit": "%",      "device_id": "ESP32-01" },
  "SOIL-HUM-02":  { "variable": "humedad_suelo_2",       "unit": "%",      "device_id": "ESP32-01" },
  "SOIL-HUM-03":  { "variable": "humedad_suelo_3",       "unit": "%",      "device_id": "ESP32-01" },
  "SOIL-TEMP-01": { "variable": "temperatura_suelo_1",   "unit": "C",      "device_id": "ESP32-01" },
  "SOIL-TEMP-02": { "variable": "temperatura_suelo_2",   "unit": "C",      "device_id": "ESP32-01" },
  "SOIL-TEMP-03": { "variable": "temperatura_suelo_3",   "unit": "C",      "device_id": "ESP32-01" },
  "NPK-N-01":     { "variable": "nitrogeno_suelo",       "unit": "mg/kg",  "device_id": "ESP32-01" },
  "NPK-P-01":     { "variable": "fosforo_suelo",         "unit": "mg/kg",  "device_id": "ESP32-01" },
  "NPK-K-01":     { "variable": "potasio_suelo",         "unit": "mg/kg",  "device_id": "ESP32-01" },
  "HR-01":        { "variable": "pulso_cardiaco",        "unit": "bpm",    "device_id": "EVA-01" },
  "SPO2-01":      { "variable": "saturacion_oxigeno",   "unit": "%",      "device_id": "EVA-01" },
  "BTEMP-01":     { "variable": "temperatura_corporal",  "unit": "C",      "device_id": "EVA-01" },
  "EVA-TEMP-01":  { "variable": "temperatura_traje",     "unit": "C",      "device_id": "EVA-01" },
  "EVA-HUM-01":   { "variable": "humedad_traje",         "unit": "%",      "device_id": "EVA-01" },
  "EVA-PRESS-01": { "variable": "presion_traje",         "unit": "hPa",    "device_id": "EVA-01" },
  "ACC-X-01":     { "variable": "aceleracion_x",         "unit": "m/s²",   "device_id": "EVA-01" },
  "ACC-Y-01":     { "variable": "aceleracion_y",         "unit": "m/s²",   "device_id": "EVA-01" },
  "ACC-Z-01":     { "variable": "aceleracion_z",         "unit": "m/s²",   "device_id": "EVA-01" },
  "ACTIVITY-01":  { "variable": "actividad",             "unit": "código", "device_id": "EVA-01" }
}
```

---

## 4. Consultar el catálogo en vivo

```bash
curl http://localhost:8000/sensors/catalog
```

Devuelve el catálogo completo **más** los contratos de lectura, buffer, ACK y MQTT.
Es la misma fuente que usa este documento — si cambia uno, cambia el otro.
