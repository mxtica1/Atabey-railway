# Prompt — Módulo 4: sensores del tripulante

Lee `AGENTS.md` en la raíz del repo antes de empezar. Respeta el contrato de datos y el stack técnico definidos ahí.

## Objetivo
Extender la simulación del tramo ESP32→LoRa→gateway para incluir un segundo dispositivo — la mochila EVA de un tripulante — con sus propios sensores biométricos, ambientales y de movimiento, reusando el mismo pipeline de ingesta (cola SQLite → sync → Mosquitto → backend → Postgres) que ya sirve al domo. Al terminar, cada `sensor_id` nuevo debe ser consultable en `GET /readings/latest?sensor_id=<id>`, y los 13 `sensor_id` del domo deben seguir funcionando exactamente igual que antes.

## Contexto
- Ya en pie y **no se tocan**: `backend/` completo, `queue.py`, `sync.py`. El patrón a reusar es el mismo de `domo_sensors.py` (clase `SensorGenerator` + función fábrica) — sigue esa misma estructura para el tripulante en vez de inventar una nueva.
- Crea `gateway/tripulante_sensors.py` con `make_tripulante_sensors()`, análogo a `make_domo_sensors()`.
- Crea `gateway/eva_receiver_sim.py`, análogo a `lora_receiver_sim.py`, que orqueste estos generadores y llame al mismo `enqueue_reading()` ya existente. Cadencia: 5s por sensor, igual que el domo.
- `gateway.py` **sí puede tocarse**, pero solo para arrancar este nuevo orquestador en paralelo al del domo — no cambies su manejo de señales (SIGINT/SIGTERM) ni la inicialización de la cola/sync.
- `device_id`: usa uno nuevo, distinto al del domo (ej. `EVA-01`), representando la mochila de un solo tripulante simulado.
- Sensores nuevos y supuestos de simulación:

| sensor_id | Mide | Unidad | Rango simulado | Notas |
|---|---|---|---|---|
| `HR-01` | Ritmo cardíaco (MAX30105) | `bpm` | 55–140 | Variación gradual, no saltos |
| `SPO2-01` | Saturación de oxígeno (MAX30105) | `%` | 92–100 | |
| `BTEMP-01` | Temperatura corporal IR (MLX90614) | `°C` | 34.5–37.5 | |
| `EVA-TEMP-01` | Temp. ambiente mochila (BME280) | `°C` | 15–35 | Dentro de los límites de regulación 13–37 °C ya definidos en el sistema térmico |
| `EVA-HUM-01` | Humedad ambiente mochila (BME280) | `%` | 30–70 | |
| `EVA-PRESS-01` | Presión ambiente mochila (BME280) | `hPa` | 950–1030 | |
| `ACC-X-01`, `ACC-Y-01`, `ACC-Z-01` | Aceleración lineal 3 ejes (BNO055, compensada por gravedad) | `m/s²` | -3 a 3 | |
| `ACTIVITY-01` | Estado de actividad (BNO055) | `código` (sin unidad) | Entero 0–3 | `0=Still, 1=Walking, 2=Running, 3=Tilting`. A diferencia de los demás, el valor debe sostenerse entre 20–60s antes de cambiar (no debe cambiar cada 5s), aunque siga publicando cada 5s. Documenta el mapeo código→estado en el README. |

  Supuestos a marcar como pendientes, no como definitivos:
  1. **ECG crudo (AD8232) queda fuera** — es forma de onda continua, no un escalar; no cabe en el contrato actual. Anótalo en `AGENTS.md` como módulo futuro, igual que las imágenes de planta.
  2. **Giroscopio, magnetómetro y orientación por cuaterniones del BNO055 quedan fuera de este módulo** — no estaban en el alcance pedido; se agregan después con el mismo patrón si se necesitan.
  3. **`ACTIVITY-01` es el primer sensor no continuo del sistema** (código entero, no medición física). Si el equipo prefiere modelarlo distinto (ej. como texto), confírmalo antes de propagar el patrón a otros sensores categóricos.
  4. **Un solo tripulante/`device_id` en este corte.** Simular varios tripulantes simultáneos es un módulo aparte.

## Restricciones
- No toques `backend/`, `queue.py`, ni `sync.py`.
- No cambies el comportamiento de ningún `sensor_id` del domo existente.
- No incluyas ECG crudo, giroscopio/magnetómetro/cuaterniones, ni las métricas del sistema de soporte de vida (agua, temperatura de regulación, calidad de señal, latencia) — no están en el alcance de este módulo.
- No agregues dependencias nuevas sin justificarlo en el mensaje de vuelta.

## Cómo se sabe que está terminado
- Con el stack completo corriendo (`docker compose up` + gateway), tras ~1 minuto, `GET /readings/latest?sensor_id=<id>` devuelve una lectura reciente para cada uno de los 10 `sensor_id` nuevos, y los 13 `sensor_id` del domo siguen respondiendo exactamente igual que antes (regresión, no solo adición).
- Tests automatizados que verifiquen: valores dentro de rango/unidad por sensor; `sequence` independiente por sensor; `ACTIVITY-01` sostiene su valor por el rango de tiempo definido antes de cambiar; con domo y tripulante intercalados en la cola, el drenado hacia el broker no pierde, duplica ni cruza lecturas entre `device_id` distintos.
- `README.md` de `/gateway` actualizado con la tabla de los 10 `sensor_id` nuevos, unidades, rangos, y el mapeo de códigos de `ACTIVITY-01`.
- `AGENTS.md` actualizado con los 4 supuestos pendientes de esta sección, para que no se pierdan.