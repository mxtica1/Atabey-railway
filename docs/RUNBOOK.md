# Runbook Operativo — Misión Atabey v1.0

## Startup

### Desarrollo Local (5 min)

```bash
# Terminal 1: Instalar dependencias
cd backend
pip install -r requirements.txt

# Terminal 1: Crear tablas en BD
python -c "import backend.db as db; db.create_table()"

# Terminal 2: Servicios (Docker Compose)
docker compose up -d
# Esperar 10s a que Postgres + MQTT estén ready

# Terminal 1: Validar configuración
python scripts/pre-deploy-check.py
# Debe retornar exit code 0 (verde)

# Terminal 1: Ejecutar tests
pytest backend/tests/ -v
# Debe pasar 40+ tests

# Terminal 1: Arrancar backend
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 3: Frontend (en subdirectorio)
cd frontend
npm install
npm run dev  # Puerto 5173

# Terminal 4: Simulador (opcional)
python simulator/send_buffer.py  # Envía buffers cada 5 seg
```

**URLs**:
- Backend: http://localhost:8000
- Docs OpenAPI: http://localhost:8000/docs
- Dashboard: http://localhost:5173
- WebSocket: ws://localhost:8000/ws/readings (sin auth si REQUIRE_LOGIN=false)

---

### Producción (Railway/Render/Fly.io)

```bash
# 1. Set variables de entorno en el panel del provider
SECRET_KEY              = <openssl rand -hex 32>
REQUIRE_LOGIN           = true
DEFAULT_ROL             = observador
CORS_ORIGINS            = https://tu-dashboard.com
DATABASE_URL            = postgresql://user:pass@host/db
MQTT_HOST               = mqtt.tuhost.com
MQTT_PORT               = 1883

# 2. Push a main (el provider ejecuta CI/CD)
git push origin main

# 3. Provider ejecuta automáticamente:
#    - pip install -r backend/requirements.txt
#    - python -c "import backend.db as db; db.create_table()"
#    - pytest backend/tests/ -v
#    - python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT

# 4. Verificar post-deploy
curl https://tu-api.com/health
# Esperado: {"status":"ok","timestamp":"...","uptime_seconds":...}

curl https://tu-api.com/auth/mode
# Esperado: {"requires_login":true,"default_rol":"observador","default_username":"..."}
```

---

## Troubleshooting

### 1. Backend no arranca

**Error**: `ERROR: ValidationError: SECRET_KEY de desarrollo`

```bash
# Causa: SECRET_KEY contiene "dev" o es muy corto
# Solución:
export SECRET_KEY="$(openssl rand -hex 32)"
# Luego reiniciar backend
```

---

### 2. Base de datos no accesible

**Error**: `psycopg2.errors.OperationalError: could not connect to server`

```bash
# Verificar que Docker está corriendo
docker ps | grep postgres
# Debe mostrar: atabey-postgres (RUNNING)

# Si no está corriendo:
docker compose up -d postgres

# Ver logs
docker logs atabey-postgres

# Verificar credenciales en .env
cat backend/.env | grep DATABASE_URL
```

---

### 3. MQTT no accesible

**Error**: `paho.mqtt.client: Connection refused`

```bash
# Verificar broker
docker ps | grep mosquitto
# Debe mostrar: atabey-mosquitto (RUNNING)

# Si está en la nube (ej. AWS IoT Core):
# Verificar que:
# 1. Servidor es accesible (firewall)
# 2. Puerto es correcto (por defecto 1883)
# 3. Certificados de TLS están en el lugar correcto

# Testear conexión
nc -zv mqtt.tuhost.com 1883
```

---

### 4. Rate limit en /auth/login

**Error**: `HTTP 429 Too Many Requests`

```bash
# Normal si hay >5 intentos fallidos en 15 min desde la misma IP
# Rate limiter está en memoria (se resetea con reinicio del backend)

# Solución rápida: reiniciar backend
kill -9 <PID de uvicorn>
# El rate limiter se resetea

# Solución de largo plazo: implementar Redis para rate limiter
# (fuera de scope v1.0)
```

---

### 5. Dashboard conectado pero sin datos

**Síntomas**:
- Dashboard carga
- WebSocket conectado
- Pero no hay datos en tiempo real

**Diagnóstico**:

```bash
# 1. Verificar que hay datos en BD
psql -U atabey -d atabey -c "SELECT COUNT(*) FROM readings;"
# Debe retornar un número > 0

# 2. Verificar WebSocket
curl -i -N -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  ws://localhost:8000/ws/readings
# Debe conectar (no instant disconnect)

# 3. Verificar CORS
curl -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: GET" \
  -i http://localhost:8000/health
# Debe tener headers CORS

# 4. Revisar logs del backend
# Ver si hay errores de broadcast
```

---

### 6. Simulador no envía datos

**Síntomas**: Dashboard vacío, pero backend responde

```bash
# 1. Verificar que simulador está corriendo
ps aux | grep send_buffer.py

# 2. Si no está, iniciarlo
cd simulator
python send_buffer.py

# 3. Si falla, verificar MQTT
# (ver punto 3 anterior)

# 4. Ver logs del simulador
python send_buffer.py --debug
```

---

### 7. Lectura "congelada" en el dashboard

**Síntoma**: Última lectura tiene timestamp antiguo

```bash
# 1. Verificar que el simulador/ESP32 sigue enviando
docker logs atabey-mosquitto | tail -20
# Debe haber mensajes MQTT recientes

# 2. Verificar que backend procesa
psql -U atabey -d atabey \
  -c "SELECT MAX(received_at) FROM readings;"
# Debe ser reciente (últimos 10 seg)

# 3. Si no, reiniciar backend
# Puede ser que MQTT no está escuchando
```

---

## Operaciones Comunes

### Cambiar umbral de temperatura

```bash
# Admin update threshold
curl -X PUT http://localhost:8000/admin/thresholds/TEMP-01 \
  -H "Authorization: Bearer <token_admin>" \
  -H "Content-Type: application/json" \
  -d '{
    "valor_min": 10,
    "valor_max": 40
  }'

# Respuesta esperada:
# {
#   "sensor_id": "TEMP-01",
#   "valor_min": 10,
#   "valor_max": 40,
#   "actualizado_por": "admin",
#   "actualizado_en": "2026-10-31T20:30:00Z"
# }
```

---

### Ver histórico de ACKs (auditoría)

```bash
# Últimos 10 ACKs de ESP32-01
curl "http://localhost:8000/admin/audit/acks?device_id=ESP32-01&limit=10" \
  -H "Authorization: Bearer <token_admin>"

# Respuesta:
# {
#   "acks": [
#     {
#       "id": 42,
#       "device_id": "ESP32-01",
#       "buffer_id": "buf-0042",
#       "received_at": "2026-10-31T20:30:15Z",
#       "total_items": 5,
#       "accepted": 5,
#       "rejected": 0,
#       "duplicates": 0
#     },
#     ...
#   ]
# }
```

---

### Ver cambios de configuración

```bash
# Últimos 20 cambios de umbrales
curl "http://localhost:8000/admin/audit/log?entity=umbral&limit=20" \
  -H "Authorization: Bearer <token_admin>"

# Ver quién cambió qué
# {
#   "changes": [
#     {
#       "id": 5,
#       "entity": "umbral",
#       "action": "update",
#       "entity_id": "TEMP-01",
#       "old_value": "{\"valor_min\": 15, \"valor_max\": 35}",
#       "new_value": "{\"valor_min\": 10, \"valor_max\": 40}",
#       "changed_by": "admin",
#       "changed_at": "2026-10-31T20:30:00Z"
#     }
#   ]
# }
```

---

### Exportar histórico de lecturas (backup)

```bash
# CSV con todas las lecturas
psql -U atabey -d atabey \
  -c "COPY readings TO STDOUT WITH CSV HEADER" > readings-backup.csv

# JSON (últimas 24 horas)
psql -U atabey -d atabey -c \
  "SELECT row_to_json(t) FROM readings t 
   WHERE received_at > NOW() - INTERVAL '24 hours';" > readings-24h.json

# SQL dump completo
pg_dump atabey > atabey-backup.sql
```

---

### Resolver alerta manualmente

```bash
# Admin resuelve alerta
curl -X PATCH http://localhost:8000/alerts/42/resolve \
  -H "Authorization: Bearer <token_admin>"

# Backend registra en audit_log:
# entity=alerta, action=resolve, entity_id=42, changed_by=admin
```

---

### Crear nuevo usuario

```bash
# Admin crea usuario
curl -X POST http://localhost:8000/admin/users \
  -H "Authorization: Bearer <token_admin>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "eva-control",
    "password": "temporal123",
    "rol": "control_mision"
  }'

# Respuesta:
# {
#   "id": 4,
#   "username": "eva-control",
#   "rol": "control_mision"
# }

# El usuario se logea:
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=eva-control&password=temporal123"
```

---

## Monitoreo & Alertas

### Métricas Clave (en producción)

1. **Latencia de ingesta**
   - Target: <100ms de lectura a BD
   - Alerta: >500ms

2. **Tasa de ACK**
   - Target: 99%+ de buffers confirmados
   - Alerta: <95%

3. **Errores de BD**
   - Target: 0 conexiones fallidas
   - Alerta: >1 error/hora

4. **Disponibilidad**
   - Target: 99.9% uptime
   - Alerta: <99%

### Dashboard de Prometheus (futuro)

```yaml
# prometheus.yml (no incluido en v1.0)
scrape_configs:
  - job_name: 'atabey-backend'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

---

## Incident Response

### Pérdida de datos (sensor sin conectar)

**Investigación**:
```bash
# 1. Verificar última lectura
psql -U atabey -d atabey \
  -c "SELECT MAX(timestamp) FROM readings WHERE sensor_id='TEMP-01';"

# 2. Verificar buffer recibido en ese período
psql -U atabey -d atabey \
  -c "SELECT * FROM ingest_ack_audit 
       WHERE received_at BETWEEN '...' AND '...';"

# 3. Si hay ACK pero no readings: bug de ingesta (escalada a devs)
# 4. Si no hay ACK: sensor/ESP32 desconectado (hardware issue)
```

---

### Latencia alta

**Diagnóstico**:
```bash
# 1. CPU/Memoria del servidor
top

# 2. Conexiones DB
psql -U atabey -d atabey \
  -c "SELECT datname, count(*) FROM pg_stat_activity GROUP BY 1;"

# 3. Queries lentas en PostgreSQL
psql -U atabey -d atabey \
  -c "SELECT query, calls, mean_exec_time FROM pg_stat_statements 
       ORDER BY mean_exec_time DESC LIMIT 5;"

# Solución: agregar índices si es necesario
```

---

## Checklist de Seguridad Semanal

- [ ] Revisar audit_log para cambios inesperados
- [ ] Verificar que REQUIRE_LOGIN=true en producción
- [ ] Confirmar que SECRET_KEY no está en el código
- [ ] Revisar CORS_ORIGINS (debe estar limitado)
- [ ] Backup automático ejecutado
- [ ] No hay usuarios semilla en producción

---

## Escalado (v1.1+)

Si necesitas:
- ✓ Multi-usuario concurrente (5→50+): Redis para sessions
- ✓ Histórico >1 año: particionamiento de readings
- ✓ LoRa/NB-IoT: agregar layer de gateway local
- ✓ Tiempo real <100ms: cambiar de REST a gRPC
- ✓ Mobile app: agregar endpoint `/api/v2` (versionado)

---

## Soporte & Contacto

- **Bugs**: GitHub Issues en repo
- **Questions**: README.md del proyecto
- **Emergency**: Reiniciar backend (soluciona 90% de problemas)
