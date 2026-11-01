Prompt — Módulo 12: coordenadas del tripulante (backend)

Lee `AGENTS.md` en la raíz del repo antes de empezar. Respeta el contrato de datos y el stack técnico definidos ahí.

## Objetivo
Agregar un pipeline de posición GPS del tripulante (lat/lon) que llegue al backend, se persista con histórico, y se transmita por WebSocket en tiempo real — como una entidad nueva y separada del contrato de `SensorReading` (una coordenada es un par de valores, no un escalar, igual que se decidió con NPK). Al terminar, `GET /locations/latest?device_id=EVA-01` debe devolver la posición más reciente, y el WS debe emitir cada actualización con `type: "location"`.

## Contexto
- Ya en pie —**no reconstruir**—: `mqtt_client.py` (patrón de suscripción por tópico, ya extendido para domo + EVA), `ws_manager.py` (broadcast con discriminador `type`, hoy `"reading"` y `"alert"`), la tabla `readings` (histórico completo, nunca se sobreescribe) como precedente de diseño.
- Nueva entidad `LocationUpdate` (Pydantic), distinta de `SensorReading`: `device_id`, `timestamp`, `lat`, `lon`, `sequence`. No reutilices el campo `value` de `SensorReading` para esto — son conceptos distintos.
- Nuevo tópico MQTT siguiendo el mismo patrón que ya usas para EVA (ej. `atabey/eva/{device_id}/location` — ajústalo al patrón real que ya tengas).
- Nueva tabla `locations` en Postgres, con histórico completo (mismo criterio que `readings`) e índice por `device_id` + `timestamp`, para poder mostrar tanto la posición actual como, más adelante, un recorrido.
- Nuevo endpoint `GET /locations/latest?device_id=` (mismo patrón que `/readings/latest`).
- Acceso por rol: la posición del tripulante **no** se trata como dato biométrico — cualquier rol autenticado la ve, igual que la telemetría técnica. Si prefieres restringirla como los signos vitales, dilo explícitamente y ajusta `BIOMETRIC_SENSORS`/el criterio de filtrado.
- Simulador: agrega un generador de posición tipo "random walk" acotado a un radio alrededor de una coordenada base (por ahora un placeholder en República Dominicana — reemplázala si tienes las coordenadas reales del sitio de la misión), publicando cada 5s en el mismo tópico de location, con `sequence` incremental propio.
- El sistema está pensado para un solo tripulante (`EVA-01`) hoy, pero diseña `locations`/el endpoint indexados por `device_id`, no hardcodeados a uno solo, para que agregar un segundo tripulante más adelante no requiera rehacer el esquema.

## Restricciones
- No toques `SensorReading` ni el contrato de 6 campos existente — esto es una entidad paralela.
- No implementes todavía el mapa ni ningún cambio de frontend — es un módulo aparte.
- No agregues dependencias nuevas sin justificarlo.

## Cómo se sabe que está terminado
- El simulador de posición corriendo publica coordenadas que llegan a Postgres y son consultables vía `GET /locations/latest?device_id=EVA-01`.
- El WS entrega mensajes `type: "location"` en tiempo real, sin romper el manejo existente de `"reading"` y `"alert"`.
- Tests: validación del modelo `LocationUpdate`; inserción y consulta de `locations`; el WS entrega `location` a todos los roles (o al rol que decidas, si restringes el acceso).
- La suite completa de regresión sigue en verde.