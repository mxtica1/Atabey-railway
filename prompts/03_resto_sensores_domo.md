# Prompt — Módulo 3: resto de sensores del domo

Lee `AGENTS.md` en la raíz del repo antes de empezar. Respeta el contrato de datos y el stack técnico definidos ahí.

## Objetivo
Extender la simulación del tramo ESP32→LoRa→gateway para que, además de TEMP-01, genere y entregue lecturas del resto de los sensores del domo que lista `AGENTS.md` (humedad de aire, CO2, luz, humedad y temperatura de suelo, NPK), reusando sin cambios el pipeline ya construido (cola SQLite → sync → Mosquitto → backend → Postgres). Al terminar, cada sensor_id nuevo debe ser consultable en `GET /readings/latest?sensor_id=<id>` con una lectura reciente, igual que TEMP-01 hoy.

## Contexto
- Ya en pie y **no se tocan**: `backend/` completo (el contrato ya es genérico por `sensor_id`, no debería requerir cambios), y de `/gateway`: `queue.py` (cola SQLite, idempotente por `sensor_id`+`sequence`), `sync.py` (drena hacia Mosquitto con backoff) y `gateway.py` (proceso principal). Si algo de esto SÍ necesita tocarse para soportar múltiples sensores, dilo explícitamente en el mensaje de vuelta en vez de asumir y cambiarlo.
- Generaliza `lora_receiver_sim.py` (o agrega un módulo nuevo, ej. `domo_sensors.py`, con la lista de generadores y que `lora_receiver_sim.py` orqueste) para que cada sensor tenga su propio generador de valores realistas, su propio contador de `sequence` independiente (nunca compartido entre sensores), y llame al mismo `enqueue_reading()` que ya usa TEMP-01. Mantén la cadencia de 5s por sensor, igual que TEMP-01.
- Sensores nuevos y supuestos de simulación (ajústalos si no calzan con lo que ya tienes definido en tu contrato):

| sensor_id | Mide | Unidad | Rango simulado |
|---|---|---|---|
| `HUM-01` | Humedad del aire | `%` | 40–85 |
| `CO2-01` | CO2 | `ppm` | 400–1200 |
| `LUX-01` | Luz (TSL2591) | `lux` | 100–3000 |
| `SOIL-HUM-01`, `SOIL-HUM-02`, `SOIL-HUM-03` | Humedad de suelo (3 por domo) | `%` | 20–70 |
| `SOIL-TEMP-01`, `SOIL-TEMP-02`, `SOIL-TEMP-03` | Temperatura de suelo (mismo sensor STEMMA, 3 por domo) | `°C` | 15–30 |
| `NPK-N-01`, `NPK-P-01`, `NPK-K-01` | Nitrógeno, Fósforo, Potasio | `mg/kg` | N: 50–300, P: 20–150, K: 100–400 |

  Supuestos a marcar como pendientes de confirmar con el equipo de hardware, no como definitivos:
  1. **NPK no tiene sensor documentado.** El listado de componentes del domo solo incluye un sensor de pH (Atlas Scientific); no hay un sensor NPK físico listado en ningún documento del proyecto. Se simula igual para no bloquear el desarrollo del dashboard, pero antes del Módulo 5 hay que confirmar si este dato vendrá de un sensor real, de entrada manual, o si se descarta del MVP.
  2. **Luz se renombra de `UV-01` a `LUX-01`.** El TSL2591 mide lux (visible + infrarrojo), no un índice UV — el nombre `UV-01` no corresponde a lo que el sensor físico realmente entrega. Si `AGENTS.md` ya tiene `UV-01` referenciado en otro lado, actualízalo ahí también para que no queden dos nombres para el mismo sensor.
  3. **Temperatura de suelo se agrega en este módulo, no después.** El STEMMA Soil Sensor mide humedad y temperatura en la misma lectura física; como el contrato solo permite un `value` por lectura, se modela igual que NPK: un `sensor_id` por cada magnitud.
- `device_id`: usa el mismo que ya usas para `TEMP-01` (todos comparten el ESP32 del domo).

## Restricciones
- No toques `backend/`, ni la lógica interna de `queue.py`/`sync.py` — solo agrega generadores que llamen a la ingesta ya existente.
- No rompas ni cambies el comportamiento de `TEMP-01`; debe seguir funcionando igual.
- No incluyas pH, actuadores (LED grow light, bomba peristáltica), presión atmosférica del domo, ni telemetría de imágenes de planta — no están en el alcance de este módulo.
- No agregues dependencias nuevas sin justificarlo en el mensaje de vuelta.

## Cómo se sabe que está terminado
- Con el stack completo corriendo (`docker compose up` + gateway), tras ~1 minuto, `GET /readings/latest?sensor_id=<id>` devuelve una lectura reciente para cada uno de los 12 `sensor_id` nuevos, además de que `TEMP-01` sigue respondiendo igual que antes.
- Tests automatizados (sin Docker) que verifiquen: cada generador produce valores dentro de su rango y unidad; cada sensor mantiene su propio `sequence` incremental sin mezclarse con los de otros sensores; con varios `sensor_id` intercalados en la cola, el drenado hacia el broker remoto no pierde, duplica ni cruza lecturas entre sensores.
- `README.md` de `/gateway` actualizado con la tabla de los `sensor_id` nuevos, su unidad y su rango simulado.