# AGENTS.md — Misión Atabey: Telemetría Domo + Tripulante

## Qué es este proyecto
Sistema de telemetría para Misión Atabey 1 (misión análoga espacial dominicana). Recoge datos de sensores del domo geodésico de cultivo y de los tripulantes, los transmite desde ESP32 por LoRa hasta un gateway, y los visualiza en un dashboard en tiempo real para el equipo de control de misión.

Dos flujos de datos comparten el mismo pipeline:
- **Domo**: temperatura y humedad de aire, CO2/O2, luz (lux, TSL2591), humedad de suelo, NPK
- **Tripulante**: pulso cardíaco, temperatura corporal, temperatura de soporte de vida, agua potable en mochila, orientación (IMU: giroscopio + acelerómetro)

## Arquitectura (offline-first)
```
Sensor → ESP32 → LoRa 433MHz → Gateway (Raspberry Pi, cola local SQLite)
  → [Internet] → MQTT → Backend (FastAPI) → PostgreSQL → Dashboard
```
Regla de oro: **ningún corte de Internet debe detener la adquisición ni provocar pérdida de telemetría.** El gateway siempre escribe primero en su cola SQLite local; sincroniza con la nube cuando hay conexión.

MQTT es el canal principal para telemetría continua. REST se usa para consultas del dashboard, autenticación y configuración/administración.

## Estructura del repo (crear a medida que avancen los módulos)
- `/simulator` — simuladores de sensores (stand-in del ESP32 mientras no hay hardware)
- `/gateway` — lógica de cola local SQLite + sincronización (Raspberry Pi)
- `/backend` — FastAPI: ingesta MQTT, API REST, modelos, PostgreSQL
- `/dashboard` — frontend
- `/firmware` — `.ino` por sensor, cuando el hardware esté disponible
- `/prompts` — prompts por módulo para Codex (numerados)
- `/docs` — contratos de datos y diagramas

## Contrato de datos — fuente de verdad, no modificar sin acuerdo del equipo de hardware
Cada lectura de sensor sigue esta estructura exacta:
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
- `sequence` es un contador incremental por sensor, para detectar lecturas perdidas.
- Frecuencia de muestreo configurable; por defecto, una lectura cada 5 segundos por sensor.

## Stack técnico (decidido)
- Backend: Python + FastAPI
- Mensajería: MQTT (Mosquitto para desarrollo local) + REST
- Base de datos: PostgreSQL, histórico completo de cada lectura (nunca solo el último valor)
- Gateway: Raspberry Pi con cola local SQLite
- Umbrales de alerta (ej. 13–37 °C del traje): siempre parámetros configurables, nunca hardcodeados

## Dashboard
Audiencia principal: equipo de control de misión. Roles con permisos diferenciados: **Administrador**, **Control de misión**, **Observador**. Los datos biométricos de tripulantes requieren acceso restringido, separado de la telemetría técnica (acceso operativo). MVP diseñado para 5–10 usuarios concurrentes.

Debe mostrar por sensor/módulo: valor actual, histórico, estado de conexión, última actualización, alertas activas, y el tripulante o módulo asociado.

Paneles ya bocetados:
- **Soporte de tripulantes**: selector de tripulante activo, orientación 3D vía IMU, signos vitales (pulso, temp. corporal, temp. soporte de vida, agua potable), comunicaciones y entorno (humedad, presión, calidad de señal, latencia)
- **Monitoreo del domo**: vista del domo geodésico, telemetría ambiental (temp./humedad aire, CO2/O2, luz (lux, LUX-01)), suelo y nutrientes (humedad, N, P, K)

## Convenciones
- Cada módulo se construye y prueba de forma aislada antes de integrarlo con el resto.
- No modificar el contrato de datos sin decirlo explícitamente en el mensaje.
- No introducir dependencias nuevas sin justificarlo.

## Qué significa "terminado"
- El código corre localmente sin intervención manual (`docker compose up` cuando aplique).
- Existe al menos una prueba automatizada del comportamiento esperado.
- Si la tarea toca el pipeline de datos, una lectura de principio a fin (sensor → dashboard) es visible y verificable.

## Supuestos técnicos y pendientes de hardware
- **Domo / NPK**: no hay sensor físico documentado en el proyecto. Simulado para no bloquear desarrollo; confirmar antes de Módulo 5 si vendrá de sensor real, entrada manual o se descarta.
- **Domo / Suelo**: STEMMA Soil Sensor mide humedad y temperatura física conjunta; se modelan como magnitudes separadas (`SOIL-HUM-*` y `SOIL-TEMP-*`).
- **Domo / Luz**: TSL2591 mide lux (`LUX-01`, visible + infrarrojo), no índice UV.
- **Tripulante / ECG crudo (AD8232)**: queda fuera del alcance actual por ser una onda continua en streaming (no escalar); se documenta como módulo futuro, análogo a imágenes de domo.
- **Tripulante / BNO055**: en Módulo 4 solo se incluye aceleración lineal 3 ejes (`ACC-X/Y/Z-01`) y estado de actividad (`ACTIVITY-01`). Giroscopio, magnetómetro y cuaterniones quedan para módulos posteriores.
- **Tripulante / ACTIVITY-01**: primer sensor discreto/categórico (código entero 0–3: `0=Still, 1=Walking, 2=Running, 3=Tilting`), sostenido 20–60 s. Confirmar si se prefiere cadena de texto a futuro.
- **Tripulante / Concurrencia**: un único tripulante simulado (`EVA-01`) en este corte; soporte multi-tripulante concurrente es un módulo aparte.

## Plan de módulos (orden sugerido)
1. Walking skeleton: un sensor simulado → MQTT → backend → PostgreSQL → endpoint de lectura (ver `/prompts/01-domo-temperatura-mvp.md`)
2. Cola offline SQLite en el gateway + lógica de sincronización
3. Resto de sensores del domo
4. Sensores del tripulante
5. Dashboard real (roles, alertas, histórico)