# Prompt — Módulo 1: walking skeleton, sensor de temperatura del domo

Lee `AGENTS.md` en la raíz del repo antes de empezar. Respeta el contrato de datos y el stack técnico definidos ahí.

## Objetivo
Construir el pipeline de telemetría de extremo a extremo para un solo sensor —temperatura del aire del domo— usando datos simulados, para validar la arquitectura completa antes de escalar al resto de los sensores. Al terminar, una lectura generada por el simulador debe llegar, en segundos, a un endpoint que devuelve el valor más reciente.

## Contexto
- Stack: Python 3.11+, FastAPI, MQTT (Mosquitto local para desarrollo), PostgreSQL. Usa Docker Compose para levantar Postgres y Mosquitto localmente sin instalación manual.
- No hay hardware ESP32 disponible todavía. En `/simulator`, crea un script que publique lecturas de temperatura realistas (rango 15–35 °C, variación gradual, no saltos aleatorios) cada 5 segundos al tópico MQTT `atabey/domo/TEMP-01`, siguiendo exactamente el esquema JSON del contrato de datos.
- En `/backend`, crea el servicio FastAPI: se suscribe al tópico MQTT, valida cada mensaje contra el esquema (usa Pydantic), y lo guarda en PostgreSQL en una tabla `readings` indexada por `sensor_id` + `timestamp`.
- Expón `GET /readings/latest?sensor_id=TEMP-01` devolviendo la última lectura almacenada.

## Restricciones
- No implementes todavía: LoRa, ESP32 real, Raspberry Pi, la cola SQLite de sincronización offline, autenticación, ni el resto de los sensores — eso son módulos siguientes. Este prompt es intencionalmente el corte más angosto posible del pipeline completo.
- No cambies el esquema del contrato de datos (`device_id`, `sensor_id`, `timestamp`, `value`, `unit`, `sequence`).
- No agregues dependencias fuera de las mencionadas sin justificarlo.
- El simulador y el backend son procesos independientes — no los acoples en un mismo script.

## Cómo se sabe que está terminado
- `docker compose up` levanta Postgres y Mosquitto sin pasos manuales adicionales.
- Corriendo el simulador y el backend en paralelo, `GET /readings/latest?sensor_id=TEMP-01` devuelve, en menos de 5 segundos, una lectura con timestamp reciente.
- Hay al menos una prueba automatizada que verifica: (a) un mensaje bien formado se guarda correctamente, y (b) un mensaje que no respeta el esquema se rechaza sin tumbar el backend.
- Un `README.md` corto en `/backend` documenta los comandos para correrlo.