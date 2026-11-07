# ✅ MAPEO CONFIRMADO: Sensores Vantroi → Sistema Atabey

**Confirmado:** 6 Nov 2026 - 22:15 UTC  
**Con:** Vantroi  
**Estado:** ✅ LISTO PARA PRODUCCIÓN

---

## 📋 Sensores Vantroi: 5 Dispositivos, 11 Mediciones

### 1. Sensor Ambiental (BMP/BME280)

| Mide | sensor_id | unit | device_id | Ubicación Dashboard |
|------|-----------|------|-----------|---|
| Temperatura Ambiente | `TEMP-01` | C | EVA-01 | Tripulante → Traje |
| Humedad Relativa | `HUM-01` | % | EVA-01 | Tripulante → Traje |
| Presión Atmosférica | `EVA-PRESS-01` | hPa | EVA-01 | Tripulante → Traje |

### 2. Sensor Cardiaco (MAX30102)

| Mide | sensor_id | unit | device_id | Ubicación Dashboard |
|------|-----------|------|-----------|---|
| Pulso Cardiaco (ECG) | `HR-01` | bpm | EVA-01 | Tripulante → Signos Vitales |

### 3. Sensor de Movimiento (BNO055/MPU6050)

| Mide | sensor_id | unit | device_id | Ubicación Dashboard |
|------|-----------|------|-----------|---|
| Aceleración X | `ACC-X-01` | m/s² | EVA-01 | Tripulante → Movimiento |
| Aceleración Y | `ACC-Y-01` | m/s² | EVA-01 | Tripulante → Movimiento |
| Aceleración Z | `ACC-Z-01` | m/s² | EVA-01 | Tripulante → Movimiento |
| Inclinación* | `ACTIVITY-01` | código | EVA-01 | Tripulante → Movimiento |
| Velocidad Angular** | ❌ NO MAPEADO | — | — | — |

*Inclinación: mapeada temporalmente a ACTIVITY-01 (0=Still, 1=Walking, 2=Running, 3=Tilting)  
**Velocidad Angular: sin sensor_id definido — se puede agregar en versión futura

### 4. Sensor de Temperatura Corporal

| Mide | sensor_id | unit | device_id | Ubicación Dashboard |
|------|-----------|------|-----------|---|
| Temperatura Corporal | `BTEMP-01` | C | EVA-01 | Tripulante → Signos Vitales |

### 5. Sensor de Luz (TSL2591)

| Mide | sensor_id | unit | device_id | Ubicación Dashboard |
|------|-----------|------|-----------|---|
| Intensidad Luminosa | `LUX-01` | lux | ESP32-01 | Domo → Ambiente |

---

## 🎯 DATOS ESPERADOS EN DASHBOARD

### Panel TRIPULANTE (EVA-01)

**Signos Vitales:**
```
Pulso: [HR-01] bpm
Temperatura Corporal: [BTEMP-01] °C
```

**Soporte de Vida (Traje EVA):**
```
Temperatura: [TEMP-01] °C
Humedad: [HUM-01] %
Presión: [EVA-PRESS-01] hPa
```

**Movimiento:**
```
Aceleración X: [ACC-X-01] m/s²
Aceleración Y: [ACC-Y-01] m/s²
Aceleración Z: [ACC-Z-01] m/s²
Actividad: [ACTIVITY-01] (código 0-3)
```

### Panel DOMO (ESP32-01)

**Ambiente:**
```
Iluminación: [LUX-01] lux
```

---

## 📝 JSON EXACTO PARA CADA LECTURA

**Endpoint:** `POST https://atabey-backend-k7kh.onrender.com/readings/single`

**Template:**
```json
{
  "device_id": "EVA-01",
  "sensor_id": "[sensor_id del mapeo]",
  "timestamp": "[ISO-8601 UTC, ej: 2026-11-06T22:15:30Z]",
  "value": [número],
  "unit": "[unidad exacta del mapeo]",
  "sequence": [contador incremental por sensor]
}
```

**Ejemplos Reales:**

Pulso (HR-01):
```json
{
  "device_id": "EVA-01",
  "sensor_id": "HR-01",
  "timestamp": "2026-11-06T22:15:30Z",
  "value": 75.0,
  "unit": "bpm",
  "sequence": 1
}
```

Temperatura Corporal (BTEMP-01):
```json
{
  "device_id": "EVA-01",
  "sensor_id": "BTEMP-01",
  "timestamp": "2026-11-06T22:15:35Z",
  "value": 36.8,
  "unit": "C",
  "sequence": 2
}
```

Aceleración X (ACC-X-01):
```json
{
  "device_id": "EVA-01",
  "sensor_id": "ACC-X-01",
  "timestamp": "2026-11-06T22:15:40Z",
  "value": 0.85,
  "unit": "m/s²",
  "sequence": 3
}
```

Iluminación (LUX-01 - DOMO):
```json
{
  "device_id": "ESP32-01",
  "sensor_id": "LUX-01",
  "timestamp": "2026-11-06T22:15:45Z",
  "value": 2500.0,
  "unit": "lux",
  "sequence": 1
}
```

---

## ✅ VERIFICACIÓN FINAL

| Aspecto | Status |
|---------|--------|
| Endpoint /readings/single | ✅ Funcionando |
| Frontend dashboard | ✅ Listo |
| Catálogo de sensores | ✅ Validado |
| Mapeo Vantroi | ✅ CONFIRMADO |
| Unidades exactas | ✅ Verificadas |
| Rangos esperados | ✅ Definidos |
| JSON estructura | ✅ Testeado |

---

## 🚀 ESTADO: LISTO PARA PRODUCCIÓN

Vantroi puede comenzar a enviar datos en cualquier momento.

Los datos aparecerán **automáticamente** en el dashboard en tiempo real.

---

## 📌 RESUMEN PARA VANTROI

**Usa EXACTAMENTE estos sensor_ids:**

```
HR-01, SPO2-01, BTEMP-01        → Signos vitales
TEMP-01, HUM-01, EVA-PRESS-01   → Traje
ACC-X-01, ACC-Y-01, ACC-Z-01    → Movimiento
ACTIVITY-01                      → Actividad
LUX-01                          → Luz (domo)
```

**device_id:**
- `"EVA-01"` para tripulante
- `"ESP32-01"` solo para LUX-01 (luz)

**Endpoint:** 
```
https://atabey-backend-k7kh.onrender.com/readings/single
```

**Unidades:** Exactamente como en la tabla arriba (C, bpm, m/s², hPa, %, lux)

¡Listo! 🎉

