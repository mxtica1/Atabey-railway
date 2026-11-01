# Prompt — Módulo 9: el dashboard consume roles y alertas

Lee `AGENTS.md` en la raíz del repo antes de empezar. Respeta el contrato de datos y el stack técnico definidos ahí.

## Objetivo
Actualizar el frontend (`Login.jsx`, `Dashboard.jsx`) para que refleje el rol del usuario autenticado y muestre las alertas activas en tiempo real, distinguiendo los mensajes de WebSocket por su campo `type` (`"reading"` vs `"alert"`). Al terminar, un Observador debe ver el panel de signos vitales oculto con un mensaje explícito de que no tiene acceso, mientras Administrador y Control de misión ven todo, alertas incluidas.

## Contexto
- Ya en pie y **no se toca**: el backend completo. `/auth/login` devuelve un JWT con claim `rol`; `/ws/readings` ahora envía mensajes con `type: "reading"` (lectura normal) o `type: "alert"` (alerta de umbral); `/alerts/active` devuelve alertas abiertas ya filtradas por rol; `BIOMETRIC_SENSORS = {HR-01, SPO2-01, BTEMP-01}` es el criterio que el backend ya usa para decidir qué es biométrico.
- `Login.jsx` hoy guarda el token pero no expone el rol al resto de la app. Decodifica el JWT en el cliente (el payload es JSON en base64, no hace falta una librería nueva) para extraer `rol` y `username`, y guárdalos junto al token en el estado de la app.
- `Dashboard.jsx` hoy solo maneja un tipo de mensaje de WS (lecturas). Actualízalo para: (a) ramificar por `type` — actualizar el valor del sensor si es `"reading"`, agregar/actualizar una entrada en un panel de "Alertas activas" si es `"alert"`; (b) mostrar el rol y usuario actual en algún lugar visible (ej. el header).
- Decisión de UX ya tomada para el panel de signos vitales cuando el rol es `observador`: se oculta por completo (no se deja vacío ni deshabilitado) y en su lugar se muestra un mensaje breve, ej. "Sin acceso a datos biométricos — rol Observador".

## Restricciones
- No toques el backend — el filtrado por rol y la lógica de alertas ya están ahí y probados (61/61).
- No implementes en este módulo gestión de usuarios ni de umbrales desde el frontend (`/admin/users`, `/admin/thresholds`) — eso es un módulo aparte.
- No agregues dependencias nuevas para decodificar el JWT — es un base64-decode simple, no hace falta librería.
- No rompas el flujo de login/WS que ya funciona para lecturas normales.

## Cómo se sabe que está terminado
- Con los tres usuarios semilla (`admin`/`admin_pass`, `mision`/`mision_pass`, `observador`/`observador_pass`), cada uno ve exactamente lo que le corresponde: Observador sin el panel de signos vitales (con el mensaje explícito) pero con el resto de sensores y sus alertas técnicas; Administrador y Control de misión ven todo, alertas biométricas incluidas.
- Una alerta activa (forzando una lectura fuera de rango, por ejemplo) aparece en el panel de "Alertas activas" sin recargar la página, distinguible visualmente de una lectura normal.
- **Verificación real en navegador, no un script**: abrir `localhost:5173`, loguearse con cada uno de los tres usuarios, y describir (o capturar) qué se ve en cada caso — esto es parte de la definición de terminado de este módulo, no un paso aparte para después.
- La suite de tests del backend se mantiene en 61/61 (no debería tocarse, pero confírmalo corriéndola).