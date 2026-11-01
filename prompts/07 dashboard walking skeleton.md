# Prompt — Módulo 5: walking skeleton del dashboard (login + 1 sensor en vivo)

Lee `AGENTS.md` en la raíz del repo antes de empezar. Respeta el contrato de datos y el stack técnico definidos ahí.

## Objetivo
Construir el pipeline de extremo a extremo del dashboard —autenticación con JWT y un valor en vivo por WebSocket— para un solo usuario, un solo rol y un solo sensor (`TEMP-01`), reusando el backend y los datos que ya llegan a Postgres. Al terminar, alguien debe poder abrir el frontend, loguearse, y ver el valor de `TEMP-01` actualizarse solo, sin recargar la página, cada vez que el gateway publique una lectura nueva.

## Contexto
- Ya en pie y funcionando: `backend/` (ingesta MQTT → Postgres, con la suscripción wildcard corregida), `gateway/` completo. No toques `gateway/` en este módulo.
- **Backend — agrega, no reemplaces:**
  - Tabla `users` en Postgres (`id`, `username`, `password_hash`, `role`). Un solo usuario semilla vía variable de entorno o script de seed — sin endpoint de registro todavía, eso es de un módulo posterior. Contraseña hasheada (ej. `passlib[bcrypt]`), nunca en texto plano.
  - `POST /auth/login`: recibe `username`/`password`, devuelve un JWT de acceso si son válidos. Usa una librería estándar para FastAPI (ej. `python-jose` + `passlib`) — justifica la elección si usas otra.
  - Endpoint WebSocket (ej. `/ws/readings`): requiere un JWT válido para conectar (rechaza la conexión si no lo tiene o es inválido). Al conectar, y por ahora, solo transmite lecturas de `TEMP-01`.
  - **Punto de arquitectura, no lo omitas:** el broadcast por WebSocket debe dispararse desde el mismo callback que ya procesa los mensajes MQTT y los escribe en Postgres — no un proceso aparte haciendo polling a la base para simular "tiempo real". Cada reading nueva de `TEMP-01` que se guarda, en el mismo flujo, se empuja a los WebSockets conectados.
  - Formato del mensaje por WS: JSON con `sensor_id`, `value`, `unit`, `timestamp` — mismo shape que ya usa el contrato, para que el patrón escale a más sensores después sin rediseñar el mensaje.
- **Frontend nuevo — `/frontend`, React + Vite:**
  - Página de login: formulario usuario/contraseña, `POST` a `/auth/login`, guarda el JWT recibido.
  - Página principal: al cargar, abre el WebSocket pasando el JWT, y muestra el valor de `TEMP-01` actualizándose en vivo conforme llegan mensajes. Sin gráficos, sin histórico, sin estilos elaborados — esto es un esqueleto, no el dashboard final.
  - Sin librerías de UI pesadas todavía (nada de Material UI, Chart.js, etc.) — eso llega cuando el dashboard real se construya sobre este esqueleto.

## Restricciones
- No implementes todavía: los otros 2 roles, clasificación biométrica/restringida/técnica, umbrales, alertas, historial de lecturas, polling de respaldo, endpoint de registro de usuarios, ni el resto de los 22 sensores. Todo eso son módulos siguientes — este es intencionalmente el corte más angosto posible del dashboard completo.
- No toques `gateway/`.
- No agregues dependencias de frontend más allá de lo que trae el scaffolding estándar de Vite + lo estrictamente necesario para JWT/WebSocket en el cliente (el `WebSocket` nativo del navegador alcanza, no uses socket.io).
- El JWT y el hash de contraseña son innegociables — nada de contraseñas en texto plano ni tokens sin firmar, ni siquiera "por ahora es solo un usuario".

## Cómo se sabe que está terminado
- Con `docker compose up` + gateway + backend + `npm run dev` del frontend corriendo, alguien puede: abrir el frontend, loguearse con el usuario semilla, y ver el valor de `TEMP-01` cambiar solo cada ~5 segundos sin recargar.
- Login con credenciales incorrectas devuelve 401, no un token.
- Una conexión al WebSocket sin JWT válido es rechazada.
- Tests automatizados del backend (con mocks, sin Docker): login exitoso devuelve un JWT válido y decodificable; login fallido devuelve 401; conexión WS sin token se rechaza; conexión WS con token válido recibe un mensaje cuando se simula una escritura nueva de `TEMP-01`.
- `README.md` de `/frontend` con los comandos para levantarlo.