# Gateway — Mision Atabey

Cola offline SQLite + sincronizacion MQTT para el gateway de la Raspberry Pi.

## Sensores del domo (Modulo 3)

| sensor_id | Magnitud | Unidad | Rango simulado |
|---|---|---|---|
| `TEMP-01` | Temperatura del aire | `C` | 15–35 |
| `HUM-01` | Humedad del aire | `%` | 40–85 |
| `CO2-01` | CO2 | `ppm` | 400–1200 |
| `LUX-01` | Luz visible+IR (TSL2591) | `lux` | 100–3000 |
| `SOIL-HUM-01` | Humedad de suelo (zona 1) | `%` | 20–70 |
| `SOIL-HUM-02` | Humedad de suelo (zona 2) | `%` | 20–70 |
| `SOIL-HUM-03` | Humedad de suelo (zona 3) | `%` | 20–70 |
| `SOIL-TEMP-01` | Temperatura de suelo (zona 1) | `C` | 15–30 |
| `SOIL-TEMP-02` | Temperatura de suelo (zona 2) | `C` | 15–30 |
| `SOIL-TEMP-03` | Temperatura de suelo (zona 3) | `C` | 15–30 |
| `NPK-N-01` | Nitrogeno | `mg/kg` | 50–300 |
| `NPK-P-01` | Fosforo | `mg/kg` | 20–150 |
| `NPK-K-01` | Potasio | `mg/kg` | 100–400 |

**Supuestos pendientes de confirmar con hardware (antes del Modulo 5):**
- **NPK-***: no hay sensor fisico documentado en el proyecto. Se simula para no bloquear el dashboard. Confirmar si vendra de sensor real, entrada manual, o se descarta del MVP.
- **SOIL-TEMP-***: el STEMMA Soil Sensor mide temperatura y humedad en la misma lectura fisica; se modela con un `sensor_id` por magnitud.
- **LUX-01**: renombrado desde `UV-01`. El TSL2591 mide lux (visible + infrarrojo), no indice UV.

## Sensores del tripulante — Mochila EVA (Modulo 4)

Dispositivo: `device_id = "EVA-01"`

| sensor_id | Magnitud / Sensor | Unidad | Rango simulado | Notas |
|---|---|---|---|---|
| `HR-01` | Ritmo cardíaco (MAX30105) | `bpm` | 55–140 | Variación gradual suave |
| `SPO2-01` | Saturación de oxígeno (MAX30105) | `%` | 92–100 | Saturación arterial |
| `BTEMP-01` | Temp. corporal IR (MLX90614) | `C` | 34.5–37.5 | Medición infrarroja |
| `EVA-TEMP-01` | Temp. ambiente mochila (BME280) | `C` | 15–35 | Regulación térmica 13–37 °C |
| `EVA-HUM-01` | Humedad ambiente mochila (BME280) | `%` | 30–70 | Humedad relativa interna |
| `EVA-PRESS-01` | Presión ambiente mochila (BME280) | `hPa` | 950–1030 | Presión atmosférica / soporte |
| `ACC-X-01` | Aceleración lineal eje X (BNO055) | `m/s²` | -3.0 a 3.0 | Compensada por gravedad |
| `ACC-Y-01` | Aceleración lineal eje Y (BNO055) | `m/s²` | -3.0 a 3.0 | Compensada por gravedad |
| `ACC-Z-01` | Aceleración lineal eje Z (BNO055) | `m/s²` | -3.0 a 3.0 | Compensada por gravedad |
| `ACTIVITY-01` | Estado de actividad (BNO055) | `código` | 0–3 | Estado discreto sostenido (20–60 s) |

### Mapeo de códigos de `ACTIVITY-01`

| Código | Estado | Descripción |
|---|---|---|
| `0` | **Still** | Tripulante estático / en reposo |
| `1` | **Walking** | Marcha / desplazamiento a paso normal |
| `2` | **Running** | Carrera / actividad de alto impacto |
| `3` | **Tilting** | Inclinación postural pronunciada |

*Nota: a diferencia de los sensores continuos, `ACTIVITY-01` retiene su valor entre 20 y 60 segundos antes de cambiar a un nuevo estado, aunque continúa emitiendo lecturas cada 5 segundos para mantener la continuidad de telemetría.*

### Supuestos pendientes de hardware (Módulo 4):
1. **ECG crudo (AD8232) queda fuera:** es una forma de onda continua en streaming, no un escalar; no cabe en el contrato JSON actual. Se documenta como módulo futuro.
2. **Giroscopio, magnetómetro y orientación (cuaterniones) del BNO055 quedan fuera:** se agregarán en un módulo posterior si control de misión lo requiere.
3. **`ACTIVITY-01` es el primer sensor categórico (no continuo):** modelado con código numérico (0–3); confirmar con hardware si se prefiere cadena de texto en el futuro.
4. **Un solo tripulante (`EVA-01`):** el soporte para múltiples tripulantes concurrentes se contempla en una fase dedicada.

## Prerequisitos

- `docker compose up` corriendo (levanta Postgres y Mosquitto).
- Backend corriendo (`uvicorn backend.main:app`).
- Dependencias instaladas:

```bash
pip install -r gateway/requirements.txt
```

## Correr el gateway

```bash
# Desde la raiz del repo
python -m gateway.gateway
```

El proceso:
1. Arranca los receptores simulados del domo (13 sensores) y de EVA-01 (10 sensores), con lecturas cada 5s.
2. Encola cada lectura en `gateway_queue.db` (SQLite, en disco).
3. Sincroniza la cola con el broker Mosquitto local, que la retransmite al backend y al dashboard.

## Pruebas automatizadas

No requieren Docker. Mockan el cliente MQTT.

```bash
# Desde la raiz del repo
pytest gateway/tests/ -v
```

## Prueba manual — corte de conexion

Esta prueba verifica el comportamiento offline-first: lecturas acumuladas durante
un corte deben llegar completas al backend cuando Mosquitto vuelve.

**Pasos:**

```bash
# 1. Levantar la infraestructura y el backend
docker compose up -d
uvicorn backend.main:app --reload

# 2. Arrancar el gateway
python -m gateway.gateway

# 3. Esperar ~30s para que se encolen varias lecturas y confirmar que llegan
curl "http://localhost:8000/readings/latest?sensor_id=TEMP-01"

# 4. Simular corte de Internet (bajar solo Mosquitto)
docker compose stop mosquitto

# 5. Esperar 2-3 minutos (varias lecturas se encolan en SQLite, no se pierden)
#    Puedes ver los pendientes en los logs del gateway:
#    "Encolado: TEMP-01 = 24.50 C  seq=42  pendientes=12"

# 6. Restaurar la conexion
docker compose start mosquitto

# 7. Verificar que todo llego: la lectura mas reciente debe tener timestamp reciente
curl "http://localhost:8000/readings/latest?sensor_id=TEMP-01"

# 8. Contar filas en Postgres para confirmar que no hay huecos
docker compose exec postgres psql -U atabey -d atabey \
  -c "SELECT COUNT(*), MIN(sequence), MAX(sequence) FROM readings WHERE sensor_id = 'TEMP-01';"
```

**Criterio de exito:**
- `MAX(sequence) - MIN(sequence) + 1 == COUNT(*)` → no hay huecos ni duplicados.
- El timestamp de la ultima lectura es reciente (pocos segundos tras el paso 7).

## Variables de entorno

| Variable   | Default         | Descripcion                      |
|------------|-----------------|----------------------------------|
| `MQTT_HOST`| `localhost`     | Host del broker MQTT remoto      |
| `MQTT_PORT`| `1883`          | Puerto del broker MQTT remoto    |
| `QUEUE_DB` | `gateway_queue.db` | Ruta a la base de datos SQLite |

Copia `.env.example` a `.env` y ajusta los valores si es necesario.
