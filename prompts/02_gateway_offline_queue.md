# Prompt — Módulo 2: cola offline SQLite en el gateway + sincronización

Lee `AGENTS.md` en la raíz del repo antes de empezar. Respeta el contrato de datos y el stack técnico definidos ahí.

## Objetivo
Construir el proceso `gateway` que representa la Raspberry Pi: cada lectura entra primero a una cola local SQLite, así nunca se pierde una lectura haya o no haya Internet. Al terminar, las lecturas generadas durante un corte de conexión al broker remoto deben aparecer completas y en orden en Postgres apenas la conexión vuelve.

## Contexto
- Ya en pie (módulo 1): `docker-compose.yml` con Postgres 16 + Mosquitto 2, y `backend/` (FastAPI, `models.py` con `SensorReading`, `db.py`, `mqtt_client.py`) suscrito a Mosquitto e insertando en Postgres. No lo toques: el `gateway` se conecta a ese mismo Mosquitto, simulando el tramo "Gateway → [Internet] → MQTT → Backend" del diagrama de `AGENTS.md`.
- Todavía no hay ESP32 ni radio LoRa reales. Simula el tramo "Sensor → ESP32 → LoRa → Gateway" con un emisor en `/gateway` (ej. `lora_receiver_sim.py`) que genera lecturas de TEMP-01 con la misma cadencia y rango del simulador del módulo 1 (15–35 °C, cada 5s) y las entrega **directo a la función de ingesta del gateway** — sin publicar por MQTT ni pasar por Mosquitto. Ese hop nunca debe depender de Internet: en la misión real, ESP32 y gateway están en el mismo sitio físico, conectados por radio corta.
- Regla de `AGENTS.md` a implementar tal cual: "el gateway siempre escribe primero en su cola SQLite local; sincroniza con la nube cuando hay conexión". Es decir: **no** intentes publicar directo al broker remoto y encolar solo si falla. Toda lectura entra primero a SQLite, sin excepción. Una tarea de sincronización aparte (loop o proceso async independiente) es la única que lee la cola e intenta publicar al broker remoto.
- La cola SQLite vive en `/gateway`, persistente en disco (no en memoria): guarda al menos `sensor_id`, `sequence`, el payload completo de la lectura y si ya fue sincronizada. Usa `sequence` (ya viene en el contrato, contador incremental por sensor) para drenar en orden y para no reencolar un duplicado si el proceso se reinicia con datos pendientes.

## Restricciones
- No toques `backend/`, `simulator/simulate_temp.py` ni el esquema del contrato de datos.
- No implementes todavía Raspberry Pi real, LoRa real, ESP32 real, el resto de los sensores, ni nada de dashboard — eso son módulos siguientes.
- La sincronización usa backoff exponencial para los reintentos de conexión al broker remoto (ej. 1s → techo de 60s); nunca descartes una lectura por número de intentos fallidos.
- No agregues dependencias nuevas sin justificarlo en el mensaje de vuelta.

## Cómo se sabe que está terminado
- El emisor simulado y el `gateway` corren como procesos de Python normales, sin más Docker que el `docker compose up` que ya levanta Postgres y Mosquitto.
- Hay pruebas automatizadas que no dependen de Docker (mockeando el cliente MQTT remoto) y cubren: toda lectura se encola al llegar, sin excepción; con "conexión" disponible la cola se vacía hacia el backend; con la conexión caída las lecturas se acumulan sin perderse; al reconectar se vacían en orden por `sequence` y sin duplicados; si el proceso del gateway se reinicia con datos pendientes, la cola sigue intacta.
- `README.md` en `/gateway` documenta una prueba manual: con todo corriendo, `docker compose stop mosquitto`, dejar pasar un par de minutos (varias lecturas encoladas), `docker compose start mosquitto`, y confirmar con `GET /readings/latest?sensor_id=TEMP-01` y un conteo de filas en Postgres que todo llegó, en orden y sin huecos ni duplicados.