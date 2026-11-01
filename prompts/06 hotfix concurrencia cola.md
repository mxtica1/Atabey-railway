# Prompt — Hotfix: condición de carrera en la cola del gateway

Lee `AGENTS.md` en la raíz del repo antes de empezar.

## Objetivo
Desde que `gateway.py` corre el orquestador del domo y el del EVA en paralelo (Módulo 4), aparecen errores intermitentes y aleatorios — `'NoneType' object is not subscriptable` dentro de `on_reading()`, y fallos de logging por `pendientes=None` — en sensores distintos cada vez. Diagnostica la causa raíz (probablemente acceso concurrente no seguro a la cola SQLite desde los hilos del domo, del EVA y de sync al mismo tiempo) y corrígela de raíz, sin ocultar el síntoma con un try/except silencioso.

## Contexto
- Evidencia del log real — el mismo tipo de error aparece en sensores distintos del domo y del EVA en momentos distintos, lo que descarta un bug específico de un sensor:
  ```
  2026-09-25 02:50:22,581 ERROR gateway.lora_receiver_sim — Error en callback on_reading (CO2-01): 'NoneType' object is not subscriptable
  2026-09-25 02:50:22,594 ERROR gateway.eva_receiver_sim — Error en callback on_reading EVA (EVA-PRESS-01): 'NoneType' object is not subscriptable
  ```
- Un segundo síntoma relacionado, capturado en un traceback completo:
  ```
  TypeError: %d format: a real number is required, not NoneType
  ...gateway.py", line 60, in on_reading
  Message: 'Encolado: [%s] %s = %s %s  seq=%d  pendientes=%d'
  Arguments: ('EVA-01', 'ACC-X-01', 0.64, 'm/s²', 10, None)
  ```
  Aquí `pendientes` llegó como `None` en vez de un entero — probablemente porque `queue.py` devuelve `None` cuando dos hilos escriben o leen el conteo de pendientes al mismo tiempo.
- Los hilos que corren en paralelo y tocan `queue.py`: el orquestador del domo (`lora_receiver_sim.py`), el del EVA (`eva_receiver_sim.py`), y el hilo de sync (`sync.py`).
- Revisa cómo `queue.py` maneja la conexión a SQLite entre hilos (¿una sola conexión compartida sin lock? ¿`check_same_thread=False` sin sincronización?). El modo WAL del Módulo 2 ayuda con lecturas concurrentes, pero no sustituye un lock si hay una sección no atómica en el código Python que calcula `pendientes` o hace el insert.

## Restricciones
- No agregues un try/except que solo silencie el error — el fix debe eliminar la condición de carrera, no ocultarla.
- No cambies el modelo de hilos completo (no migres todo a `asyncio` ni a multiprocessing) a menos que confirmes que un lock o una conexión por hilo no resuelve el problema — probá la solución más simple primero.
- Mantén el manejo de `SIGINT`/`SIGTERM` de `gateway.py` funcionando para los tres hilos (domo, EVA, sync) después del fix.

## Cómo se sabe que está terminado
- El gateway corre 2 minutos seguidos sin que aparezca ningún `ERROR` ni `Logging error` en consola.
- Un test automatizado que dispare varios hilos escribiendo a la cola al mismo tiempo (reproduciendo la condición real) y confirme que ya no se corrompe ni devuelve `None`.
- En el mensaje de vuelta, una frase explicando la causa raíz exacta (qué operación no era atómica) y por qué el fix la resuelve.