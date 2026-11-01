# Prompt — Módulo 6: roles y control de acceso

Lee `AGENTS.md` en la raíz del repo antes de empezar. Respeta el contrato de datos y el stack técnico definidos ahí.

## Objetivo
Añadir control de acceso por rol (Administrador, Control de misión, Observador) sobre la autenticación JWT que ya existe, de forma que un usuario con rol Observador nunca reciba datos biométricos del tripulante —ni por REST ni por WebSocket— y que solo Administrador pueda gestionar usuarios. Al terminar, tres usuarios de prueba con los tres roles deben tener acceso exactamente distinto al mismo stream de datos.

## Contexto
- Ya en pie del módulo 5 — **no reconstruir**: `backend/auth.py` (hasheo, JWT, `get_current_user`), `backend/db.py` (tabla `users` con el admin semilla), `backend/models.py` (`User`, `Token`, `LoginRequest`), `backend/main.py` (`/auth/login`, `/ws/readings`, CORS), `backend/ws_manager.py` (`ConnectionManager` con `broadcast_sync` puenteado desde el hilo de MQTT con `asyncio.run_coroutine_threadsafe`).
- Extiende la tabla `users` con una columna `rol` (`administrador` | `control_mision` | `observador`). El usuario semilla admin/admin_pass pasa a `rol="administrador"`. Ajusta `db.py` para que la tabla nueva/migrada tenga esta columna.
- El JWT que ya emite `/auth/login` debe incluir el rol como claim, para no consultar la base en cada mensaje del WebSocket.
- Clasificación de sensores para la regla de acceso (ajústala si no calza con lo que ya tienes construido en el módulo 4): **biométrico** = `HR-01`, `SPO2-01`, `BTEMP-01` (los tres signos vitales). Todo lo demás —domo, `EVA-TEMP-01`/`EVA-HUM-01`/`EVA-PRESS-01`, `ACC-X/Y/Z-01`, `ACTIVITY-01`— es telemetría técnica y la ve cualquier rol autenticado.
- `ConnectionManager` hoy hace `broadcast_sync` idéntico a todas las conexiones. Necesita conocer el rol de cada conexión (extraído del JWT al aceptar el WebSocket, no de una consulta aparte) para decidir, mensaje por mensaje, si se lo entrega a esa conexión.

## Restricciones
- No reconstruyas la lógica de JWT/hasheo de `auth.py` — solo agrega el claim de rol y un dependency de verificación de rol para FastAPI (ej. `require_role(...)`).
- La regla de Observador debe cumplirse en los dos caminos (REST y WebSocket), no en uno solo.
- No implementes todavía clasificación automática de datos sensibles ni alertas — son módulos aparte.
- No agregues dependencias nuevas sin justificarlo en el mensaje de vuelta.

## Cómo se sabe que está terminado
- Un usuario `observador` que hace login y abre el WebSocket nunca recibe mensajes de `HR-01`/`SPO2-01`/`BTEMP-01`, aunque el gateway los esté publicando en ese momento.
- Ese mismo usuario recibe 403 al llamar cualquier endpoint de gestión de usuarios.
- Un usuario `control_mision` o `administrador` sí recibe todo, biométrico incluido.
- Tests automatizados (sin Docker) cubren: creación de usuario con rol vía endpoint de administrador; 403 para observador en ese endpoint; filtrado de biométricos en el WS para observador (simulando un mensaje MQTT de `HR-01` y confirmando que esa conexión no lo recibe); el JWT emitido en login trae el claim de rol correcto para cada uno de los tres roles.
- `README.md` actualizado con los tres roles, los tres usuarios de prueba y qué ve cada uno.