# 📍 Mapeo de Sensores: Sistema vs Vantroi

**Fecha:** 6 Nov 2026 - 22:00 UTC  
**Propósito:** Verificación antes de envío de datos  
**Estado:** ⏳ EN ESPERA de confirmación de Vantroi

---

## ⚠️ CRÍTICO

Los datos que Vantroi envíe **SOLO aparecerán en el dashboard si los sensor_ids coinciden exactamente** con lo que el sistema espera.

---

## 📊 Catálogo Oficial del Sistema

El sistema Atabey gestiona **23 sensores totales** divididos en dos dispositivos:

### DISPOSITIVO 1: TRIPULANTE (EVA-01)
**10 sensores totales**

| sensor_id | Nombre | Unidad | Rango | Tipo | Vista |
|-----------|--------|--------|-------|------|------|
| HR-01 | Pulso Cardiaco | bpm | 55-140 | Biométrico | Tripulante |
| SPO2-01 | Saturación O₂ | % | 92-100 | Biométrico | Tripulante |
| BTEMP-01 | Temperatura Corporal | °C | 34.5-37.5 | Biométrico | Tripulante |
| EVA-TEMP-01 | Temperatura Traje | °C | 15-35 | EVA | Tripulante |
| EVA-HUM-01 | Humedad Traje | % | 30-70 | EVA | Tripulante |
| EVA-PRESS-01 | Presión Traje | hPa | 950-1030 | EVA | Tripulante |
| ACC-X-01 | Aceleración X | m/s² | -3 a +3 | IMU | Tripulante |
| ACC-Y-01 | Aceleración Y | m/s² | -3 a +3 | IMU | Tripulante |
| ACC-Z-01 | Aceleración Z | m/s² | -3 a +3 | IMU | Tripulante |
| ACTIVITY-01 | Actividad | código | 0-3 | IMU | Tripulante |

### DISPOSITIVO 2: DOMO (ESP32-01)
**13 sensores totales**

| sensor_id | Nombre | Unidad | Rango | Tipo | Vista |
|-----------|--------|--------|-------|------|------|
| TEMP-01 | Temperatura Aire | °C | 15-35 | Ambiente | Domo |
| HUM-01 | Humedad Aire | % | 40-85 | Ambiente | Domo |
| CO2-01 | Concentración CO₂ | ppm | 400-1200 | Ambiente | Domo |
| LUX-01 | Iluminación | lux | 100-3000 | Ambiente | Domo |
| SOIL-HUM-01 | Humedad Suelo Z1 | % | 20-70 | Suelo | Domo |
| SOIL-HUM-02 | Humedad Suelo Z2 | % | 20-70 | Suelo | Domo |
| SOIL-HUM-03 | Humedad Suelo Z3 | % | 20-70 | Suelo | Domo |
| SOIL-TEMP-01 | Temp. Suelo Z1 | °C | 15-30 | Suelo | Domo |
| SOIL-TEMP-02 | Temp. Suelo Z2 | °C | 15-30 | Suelo | Domo |
| SOIL-TEMP-03 | Temp. Suelo Z3 | °C | 15-30 | Suelo | Domo |
| NPK-N-01 | Nitrógeno | mg/kg | 50-300 | Nutrientes | Domo |
| NPK-P-01 | Fósforo | mg/kg | 20-150 | Nutrientes | Domo |
| NPK-K-01 | Potasio | mg/kg | 100-400 | Nutrientes | Domo |

---

## 🔄 Proceso de Mapeo

### Paso 1: Identificar Sensores en Hardware

Vantroi debe proporcionar:
1. **Listado de sensores físicos** (ej: DHT22, MAX30102, etc.)
2. **Qué mide cada uno** (temperatura, humedad, pulso, etc.)
3. **Para quién es** (tripulante o domo)

### Paso 2: Validación de Mapeo

Mapeamos 1:1 cada sensor físico con un `sensor_id` del catálogo:

**Ejemplo:**
```
Hardware: DHT22 (temperatura + humedad)
Mide: Temperatura del aire dentro del domo
→ Mapea a: TEMP-01 (unidad: C)

Hardware: MAX30102 (pulso)
Mide: Frecuencia cardíaca del tripulante
→ Mapea a: HR-01 (unidad: bpm)
```

### Paso 3: Validar Unidades

Las unidades en el JSON DEBEN coincidir con el catálogo:

```json
{
  "device_id": "EVA-01",
  "sensor_id": "HR-01",
  "value": 75,
  "unit": "bpm"  // ← DEBE ser "bpm", no "latidos/min" o "heart rate"
}
```

---

## ✅ Checklist antes de Enviar Datos

- [ ] ¿Confirmo qué sensores tengo?
- [ ] ¿Cada uno mapea a un sensor_id válido del catálogo?
- [ ] ¿Las unidades coinciden exactamente?
- [ ] ¿El device_id es correcto (EVA-01 o ESP32-01)?
- [ ] ¿El endpoint es `/readings/single`?
- [ ] ¿El JSON tiene los 6 campos requeridos?

---

## 🎯 Estado Actual

| Aspecto | Status |
|---------|--------|
| Backend pronto | ✅ /readings/single funcionando |
| Frontend listo | ✅ Dashboard pronto para datos |
| Catálogo definido | ✅ 23 sensores, estructurado |
| Mapeo Vantroi | ⏳ EN ESPERA |

---

## 📞 Próximo Paso

**Vantroi debe responder:**
1. ¿Cuántos sensores tienes y cuáles son?
2. ¿Para quién es (tripulante o domo)?
3. ¿Qué mide cada uno?

**Ej:**
```
- Sensor 1: DHT22 (temperatura + humedad) → para el domo
- Sensor 2: MPU6050 (aceleración) → para el tripulante
- Sensor 3: MAX30102 (pulso + O₂) → para el tripulante
```

Una vez confirmado, mapearemos y podrá empezar a enviar.

---

## 🚀 No Comenzar Hasta:

❌ NO enviar datos sin confirmación de sensor_ids  
❌ NO usar IDs que no estén en el catálogo  
❌ NO cambiar unidades sin preguntar  

✅ SÍ esperar confirmación del mapeo  
✅ SÍ usar exactamente los valores del catálogo  

