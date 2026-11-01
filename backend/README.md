# Backend — Atabey Telemetria

Backend FastAPI del pipeline de telemetria de Mision Atabey 1.

## Pre-requisitos

- Python 3.11+
- Docker y Docker Compose (para Postgres y Mosquitto)

## Inicio rapido

### 1. Levantar la infraestructura local

Desde la raiz del repositorio:

```bash
docker compose up -d
```

Esto levanta:
- **PostgreSQL 16** en `localhost:5433` (base de datos `atabey`, usuario `atabey`, password `atabey`)
- **Mosquitto 2** en `localhost:1883` (MQTT) y `localhost:9001` (WebSocket)

### 2. Instalar dependencias del backend

```bash
pip install -r backend/requirements.txt
```

### 3. Configurar variables de entorno (opcional)

Los valores por defecto funcionan con el docker-compose incluido.
Si necesitas personalizar, crea `backend/.env` a partir de `backend/.env.example`:

```bash
cp backend/.env.example backend/.env
```

### 4. Arrancar el backend

Desde la **raiz del repositorio**:

```bash
uvicorn backend.main:app --reload
```

El backend quedara disponible en `http://localhost:8000`.
Documentacion interactiva: `http://localhost:8000/docs`

### 5. Arrancar el simulador

En otra terminal, desde la raiz del repositorio:

```bash
pip install -r simulator/requirements.txt
python simulator/simulate_temp.py
```

Este simulador independiente publica **solo `TEMP-01`**. Para ver los 13 sensores simulados del domo y los 10 de EVA-01 en el dashboard, detén `simulate_temp.py` y arranca el gateway en otra terminal:

```bash
pip install -r gateway/requirements.txt
python -m gateway.gateway
```

El gateway simula ambos grupos y los envía por MQTT al backend, que los transmite por WebSocket. La cadencia configurada es de 5 segundos; no ejecutes ambos generadores del domo a la vez porque publicarán temperatura duplicada.

### 6. Verificar el pipeline

```bash
curl "http://localhost:8000/readings/latest?sensor_id=TEMP-01"
```

Deberia devolver la ultima lectura en menos de 5 segundos tras iniciar el simulador.

## Correr los tests

```bash
pip install pytest httpx
pytest backend/tests/ -v
```

Los tests no requieren Docker: usan mocks para la base de datos y MQTT.

## Roles y control de acceso

El sistema tiene tres roles con permisos diferenciados:

| Rol              | Ve telemetria tecnica | Ve datos biometricos | Gestiona usuarios |
|------------------|-----------------------|----------------------|-------------------|
| `administrador`  | ✓                     | ✓                    | ✓                 |
| `control_mision` | ✓                     | ✓                    | ✗                 |
| `observador`     | ✓                     | ✗                    | ✗                 |

**Sensores biometricos** (restringidos a `administrador` y `control_mision`):
`HR-01` (pulso), `SPO2-01` (saturacion de oxigeno), `BTEMP-01` (temperatura corporal).

**Telemetria tecnica** (visible para cualquier rol autenticado):
`EVA-TEMP-01`, `EVA-HUM-01`, `EVA-PRESS-01`, `ACC-X/Y/Z-01`, `ACTIVITY-01`,
y todos los sensores del domo (`TEMP-01`, `HUM-01`, etc.).

La restriccion aplica tanto a REST (`/readings/latest`) como a WebSocket (`/ws/readings`).
El rol viaja como claim dentro del JWT para evitar consultas a la BD en cada mensaje WS.

### Usuarios de prueba

Creados automaticamente al iniciar el backend (si no existen):

| Usuario      | Contrasena       | Rol              |
|--------------|------------------|------------------|
| `admin`      | `admin_pass`     | `administrador`  |
| `mision`     | `mision_pass`    | `control_mision` |
| `observador` | `observador_pass`| `observador`     |

### Endpoints de administracion (solo `administrador`)

| Metodo | Ruta                       | Descripcion                  |
|--------|----------------------------|------------------------------|
| GET    | `/admin/users`             | Lista todos los usuarios     |
| POST   | `/admin/users`             | Crea un nuevo usuario        |
| DELETE | `/admin/users/{user_id}`   | Elimina un usuario por ID    |

Payload para crear usuario:
```json
{
  "username": "nuevo",
  "password": "clave123",
  "rol": "observador"
}
```
Roles validos: `administrador`, `control_mision`, `observador`.

## Endpoints

| Metodo | Ruta                              | Auth requerida   | Descripcion                              |
|--------|-----------------------------------|------------------|------------------------------------------|
| POST   | `/auth/login`                     | —                | Emite JWT con claim de rol               |
| GET    | `/readings/latest?sensor_id=...`  | Cualquier rol    | Ultima lectura (biometricos: 403 para observador) |
| WS     | `/ws/readings?token=...`          | Cualquier rol    | Stream en tiempo real (filtrado por rol) |
| GET    | `/admin/users`                    | administrador    | Lista usuarios                           |
| POST   | `/admin/users`                    | administrador    | Crea usuario                             |
| DELETE | `/admin/users/{user_id}`          | administrador    | Elimina usuario                          |
| GET    | `/health`                         | —                | Health check                             |
| GET    | `/docs`                           | —                | Documentacion interactiva (Swagger)      |
