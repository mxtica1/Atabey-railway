# Despliegue — Misión Atabey 1

Estado actual del despliegue, las credenciales del proyecto y el procedimiento
para publicarlo en Netlify o Vercel.

---

## 1. Arquitectura en producción

El sistema tiene **dos partes** que se despliegan por separado:

| Parte | Qué es | Dónde va |
|---|---|---|
| **Frontend** | SPA de Vite (React) — solo estáticos | Netlify / Vercel |
| **Backend** | FastAPI + WebSocket + MQTT + PostgreSQL | Railway / Render / Fly.io / VPS |

El frontend es un sitio estático. El backend es un servicio con base de datos.
**El frontend necesita la URL pública del backend** para traer datos.

---

## 2. Credenciales del proyecto

### Backend (`backend/.env`)

```env
DATABASE_URL=postgresql://atabey:atabey@localhost:5433/atabey
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_TOPIC=atabey/#

SECRET_KEY=supersecretkey_for_dev_only
ALGORITHM=HS256
SEED_ADMIN_USER=admin
SEED_ADMIN_PASSWORD=admin_pass

REQUIRE_LOGIN=false
DEFAULT_ROL=administrador
DEFAULT_USERNAME=anonimo
```

| Variable | Significado |
|---|---|
| `DATABASE_URL` | Postgres. En Docker local: `localhost:5433`. En PaaS: la URL que da el proveedor. |
| `SECRET_KEY` | Firma de los JWT. **En producción: valor aleatorio largo.** |
| `SEED_ADMIN_USER` / `SEED_ADMIN_PASSWORD` | Usuario admin que se crea al primer arranque. |
| `REQUIRE_LOGIN` | `false` = dashboard público sin credenciales. `true` = login obligatorio. |
| `DEFAULT_ROL` | Rol con el que entra quien accede sin login (`administrador` \| `control_mision` \| `observador`). |
| `CORS_ORIGINS` | *(opcional)* Orígenes permitidos, separados por comas. `*` = cualquiera. En modo anónimo sin este valor ya se permite `*`. |

Usuarios semilla que crea `create_table()`:

| Usuario | Contraseña | Rol |
|---|---|---|
| `admin` | `admin_pass` | administrador |
| `control_mision` | `control_pass` | control_mision |
| `observador` | `observer_pass` | observador |

### Frontend (`frontend/.env`)

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
VITE_CARTO_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

| Variable | Significado |
|---|---|
| `VITE_API_BASE_URL` | URL base del backend (REST). |
| `VITE_WS_BASE_URL` | URL del WebSocket. Si se omite, se deriva de la anterior (`http`→`ws`, `https`→`wss`). |
| `VITE_CARTO_API_KEY` | API key de CARTO para el estilo Dark Matter sin watermark. |

> La key de CARTO ya está en `frontend/.env` del repo local. Es una key pública
> de CARTO (plan gratuito) — se embebe en el bundle del frontend de todas
> formas, no es un secreto de servidor.

### Configuración en runtime (nuevo)

Además de las variables de build, el frontend lee `public/runtime-config.js`:

```js
window.__ATABEY_CONFIG__ = {
  apiBaseUrl: 'https://tu-backend-publico',
  wsBaseUrl:  'wss://tu-backend-publico',
};
```

Este archivo **se sirve tal cual, sin compilar**. Permite cambiar la URL del
backend en un sitio ya desplegado sin recompilar ni redesplegar. En Netlify y
Vercel se sobreescribe con las variables de entorno del panel.

---

## 3. Desplegar el frontend en Netlify

### Opción A — desde el panel (sin CLI)

1. Entrar a [app.netlify.com](https://app.netlify.com) → **Add new site** → **Import an existing project**.
2. Conectar el repositorio de GitHub.
3. Netlify detecta `netlify.toml` en la raíz. Configuración:
   - **Base directory**: `frontend`
   - **Build command**: `npm run build`
   - **Publish directory**: `frontend/dist`
4. En **Site configuration → Environment variables** agregar:

   ```
   VITE_API_BASE_URL = https://tu-backend-publico
   VITE_WS_BASE_URL  = wss://tu-backend-publico
   VITE_CARTO_API_KEY = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ```

5. **Deploy site**. La URL pública queda en `https://<sitio>.netlify.app`.

### Opción B — con la CLI

```bash
npm i -g netlify-cli
netlify login
cd frontend
netlify deploy --prod --build
```

### Opción C — Vercel

```bash
npm i -g vercel
cd frontend
vercel --prod
# Vercel lee vercel.json: buildCommand "npm run build", outputDirectory "dist"
```

En Vercel, **Environment Variables** en Settings → Environment Variables:

```
VITE_API_BASE_URL = https://tu-backend-publico
VITE_WS_BASE_URL  = wss://tu-backend-publico
VITE_CARTO_API_KEY = ...
```

> Ojo: `vercel.json` está en `frontend/`, así que el **Root Directory** del
> proyecto en Vercel debe ser `frontend`.

---

## 4. Desplegar el backend

El backend necesita: FastAPI, PostgreSQL y (para el pipeline real) Mosquitto
o un broker MQTT gestionado.

### Opción A — Railway (recomendado para pruebas)

1. [railway.app](https://railway.app) → **New Project** → *Deploy from GitHub*.
2. **Add PostgreSQL** → Railway genera `DATABASE_URL` automáticamente.
3. Crear un servicio desde el repo con:
   - **Root Directory**: `backend`
   - **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. Variables de entorno:

   ```
   DATABASE_URL   = (la que da Railway)
   SECRET_KEY     = <openssl rand -hex 32>
   REQUIRE_LOGIN  = false
   DEFAULT_ROL    = administrador
   CORS_ORIGINS   = https://tu-frontend.netlify.app
   MQTT_HOST      = <broker>        # opcional
   MQTT_PORT      = 1883
   MQTT_TOPIC     = atabey/#
   ```

5. Railway da la URL: `https://<servicio>.up.railway.app`.
6. Esa URL es la que va en `VITE_API_BASE_URL` del frontend.

### Opción B — Render

1. [render.com](https://render.com) → **New + → Web Service** → conectar repo.
2. **Root Directory**: `backend`, **Runtime**: Python.
3. **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. Agregar un **PostgreSQL** de Render y setear `DATABASE_URL`.
5. Variables: `SECRET_KEY`, `REQUIRE_LOGIN=false`, `DEFAULT_ROL`, `CORS_ORIGINS`.

### Opción C — máquina local con túnel (para pruebas rápidas)

Mientras el backend corre en `localhost:8000`, se puede exponer con:

```bash
# Cloudflare quick tunnel (sin cuenta)
tools\cloudflared.exe tunnel --url http://localhost:8000
# -> https://<aleatorio>.trycloudflare.com
```

Después poner esa URL en `VITE_API_BASE_URL` / `VITE_WS_BASE_URL` y redesplegar
el frontend (o editar `runtime-config.js` en el sitio desplegado).

> Esta opción **solo funciona mientras la computadora esté encendida** y el
> proceso del túnel vivo. Para una misión real, usar la Opción A o B.

---

## 5. Verificación post-despliegue

```bash
# 1. El backend responde
curl https://tu-backend/health
# {"status":"ok"}

# 2. El modo de acceso es el esperado
curl https://tu-backend/auth/mode
# {"requires_login":false,"default_rol":"administrador","default_username":"anonimo"}

# 3. El catalogo de sensores está completo
curl https://tu-backend/sensors/catalog | head -c 200

# 4. El registro de ingesta responde
curl https://tu-backend/ingest/recent?limit=5

# 5. Un buffer entra y vuelve el ACK
python simulator\send_buffer.py
```

En el navegador, abrir la URL del frontend:
- Debe entrar **sin pantalla de login** (si `REQUIRE_LOGIN=false`).
- El mapa CARTO Dark Matter carga de fondo.
- La vista **Registro de ingesta** (icono de base de datos) lista las lecturas
  con sensor, valor, momento de medición y momento de guardado.

---

## 6. Variables de entorno del frontend: dónde ponerlas

| Plataforma | Dónde |
|---|---|
| Netlify | Site configuration → Environment variables |
| Vercel | Project → Settings → Environment Variables |
| Build local | `frontend/.env` o variables del sistema antes de `npm run build` |
| Después del deploy | Editar `runtime-config.js` en el sitio (si el proveedor lo permite) |

---

## 7. Checklist de seguridad antes de un vuelo real

- [ ] `REQUIRE_LOGIN=true` si el dashboard no debe ser público.
- [ ] `SECRET_KEY` con valor aleatorio largo (no el de desarrollo).
- [ ] `SECRET_KEY` distinto del que está en el repo.
- [ ] Contraseñas semilla cambiadas (`SEED_ADMIN_PASSWORD`, etc.).
- [ ] `CORS_ORIGINS` limitado al dominio real del frontend.
- [ ] `DEFAULT_ROL=observador` si se expone sin login (datos biométricos fuera).
- [ ] HTTPS en el backend (lo da el PaaS o el túnel).
