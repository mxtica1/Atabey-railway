# Prompt — Hotfix: suscripción MQTT del backend

Lee `AGENTS.md` en la raíz del repo antes de empezar.

## Objetivo
El backend solo recibe lecturas del sensor `TEMP-01`, porque `backend/mqtt_client.py` se suscribe a un único tópico MQTT hardcodeado. Corrige la suscripción para que reciba las lecturas de los 23 `sensor_id` actuales (13 del domo + 10 del EVA) sin listar cada tópico a mano, y sin romper lo que ya funciona.

## Contexto
- Evidencia del bug, tomada del log real de arranque del backend:
  ```
  2026-09-25 02:50:01,593 INFO backend.mqtt_client — Suscrito a atabey/domo/TEMP-01
  ```
  Es la única línea de suscripción que aparece — nunca se suscribe a nada más, así que cualquier lectura publicada bajo otro tópico (HUM-01, CO2-01, cualquier sensor del EVA, etc.) se pierde silenciosamente del lado del backend.
- Antes de tocar la suscripción, revisa qué tópico(s) publica realmente `gateway/sync.py` para cada lectura hoy — puede haber cambiado entre Módulo 1 y Módulo 3/4 al generalizar a múltiples sensores. La suscripción del backend debe calzar exactamente con el patrón real de publicación, no con uno inventado. De hecho, verifica si `TEMP-01` sigue publicándose bajo `atabey/domo/TEMP-01` o si ese tópico también cambió — en la última corrida tampoco llegó, así que no lo des por sentado.
- El contrato de datos (`device_id, sensor_id, timestamp, value, unit, sequence`) no cambia — este es un problema de tópico MQTT, no de esquema.

## Restricciones
- Esta vez sí puedes tocar `backend/mqtt_client.py` — la restricción anterior de "no tocar backend" asumía que el contrato genérico ya bastaba, y este bug demuestra que no. No toques el resto de `backend/` (modelos, endpoints, DB) salvo que el fix realmente lo requiera; si lo requiere, dilo explícito en el mensaje de vuelta.
- No hardcodees una lista de 23 tópicos — usa un patrón (wildcard MQTT `+` o `#`, según corresponda) consistente con lo que realmente se publica.
- No asumas que `TEMP-01` está bien — confírmalo con evidencia, no por herencia del Módulo 1.

## Cómo se sabe que está terminado
- Repitiendo el procedimiento completo (`docker compose down -v`, `up -d`, backend, gateway, esperar 60s, correr `e2e.py`) — debe reportar 23/23 sensores OK.
- Un test automatizado (con broker mockeado, como el resto de la suite) que confirme que el backend procesa mensajes de al menos 3 tópicos distintos con la suscripción configurada, no solo uno.
- En el mensaje de vuelta, una frase explicando cuál era el tópico real que se estaba publicando vs. el que se estaba escuchando.