# 🛑 Desactivar Simuladores - Recibir Solo Datos de Vantroi

## Situación Actual

Actualmente, el sistema puede estar ejecutando simuladores que generan datos de prueba. Para asegurar que **SOLO veas datos reales del ESP32 de Vantroi**, necesitamos desactivar todos los simuladores.

---

## Simuladores Activos

### 1. **E2E (End-to-End Tests)**
Archivo: `e2e.py`
Propósito: Tests de integración completa

### 2. **Simuladores de Sensores**
Ubicación: `simulator/`

Archivos:
- `simulate_temp.py` — Simula temperatura
- `simulate_location.py` — Simula posiciones GPS
- `send_buffer.py` — Envía buffers de prueba

---

## ✅ Checklist de Desactivación

### Paso 1: Verificar qué está corriendo
```bash
# En tu terminal, lista todos los procesos Python
tasklist | findstr python

# O en PowerShell
Get-Process | Where-Object {$_.ProcessName -like "*python*"}
```

### Paso 2: Detener Simuladores

Si tienes alguno corriendo, detente presionando **Ctrl+C** en cada terminal.

#### Si estás usando `simulator/`:
```bash
# Terminal donde ejecutaste el simulador
Ctrl+C

# Verifica que se detuvo
```

#### Si estás usando `e2e.py`:
```bash
# Si lo ejecutaste:
python e2e.py
# Presionar Ctrl+C
```

### Paso 3: Asegurar que NO se ejecutan en startup

Los simuladores probablemente **NO están corriendo automáticamente** (solo si TÚ los ejecutaste manualmente).

Verifica que no hay scripts en background:

```bash
# Terminal PowerShell
Get-Process | findstr /i python

# Debería mostrar solo:
# - Backend (python -m uvicorn)
# - Frontend (npm run dev)
# NADA MÁS
```

---

## 🔍 Verificar que Backend NO está generando datos falsos

### Revisar Código del Backend

El backend **NO genera datos simulados por defecto**. Solo recibe datos via:
1. **MQTT** (desde ESP32)
2. **REST** (endpoints como `/readings/batch`)

### Confirmar en Logs

```bash
# Terminal del backend (donde ejecutaste uvicorn)

# Debería ver:
2026-11-01 14:30:00,000 INFO  - ✓ Backend Atabey iniciado correctamente
2026-11-01 14:30:01,000 INFO  - MQTT conectado al broker localhost:1883
2026-11-01 14:30:02,000 INFO  - Suscrito a atabey/#

# NO debería ver:
# - "Simulando temperatura..."
# - "Generando datos de prueba..."
# - "enviando buffer simulado..."
```

Si ves algo sospechoso, avisa.

---

## 📊 Verificar Base de Datos

Para confirmar que NO hay datos viejos contaminando:

### Limpiar (OPCIONAL - hacer solo si quieres empezar limpio)

**ADVERTENCIA:** Esto borra TODO. Solo hazlo si Vantroi aún no ha enviado datos.

```bash
# Terminal (con venv activado)
python -c "
import backend.db as db
from backend.db import get_connection

with get_connection() as conn:
    with conn.cursor() as cur:
        # Borrar todas las lecturas
        cur.execute('DELETE FROM readings')
        # Borrar alertas
        cur.execute('DELETE FROM alerts')
        # Borrar histórico de ingesta
        cur.execute('DELETE FROM ingest_ack_audit')
        print('✓ Base de datos limpiada')
    conn.commit()
"
```

### Verificar que está limpia

```bash
python -c "
import backend.db as db
from backend.db import get_connection

with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM readings')
        count = cur.fetchone()[0]
        print(f'Total de lecturas en BD: {count}')
        
        cur.execute('SELECT COUNT(*) FROM alerts')
        alerts = cur.fetchone()[0]
        print(f'Total de alertas en BD: {alerts}')
"
```

Debería devolver:
```
Total de lecturas en BD: 0
Total de alertas en BD: 0
```

---

## 🚀 Setup Final

### Servicios que DEBEN estar corriendo:

```bash
# Terminal 1: Docker
docker compose up -d
✓ PostgreSQL: localhost:5433
✓ Mosquitto: localhost:1883

# Terminal 2: Backend
.\venv_atabey\Scripts\Activate.ps1
python -m uvicorn backend.main:app --reload --port 8000
✓ Backend: http://localhost:8000

# Terminal 3: Frontend
cd frontend && npm run dev
✓ Frontend: http://localhost:5173

# ✗ NADA MÁS
# (Nada de simuladores)
```

### Servicios que DEBEN estar PARADOS:

- ✗ `simulator/simulate_temp.py`
- ✗ `simulator/simulate_location.py`
- ✗ `simulator/send_buffer.py`
- ✗ `e2e.py`
- ✗ Cualquier otro script que genere datos

---

## 📡 Verificar que SOLO Vantroi Envía Datos

### Monitorear MQTT en tiempo real

```bash
# Terminal nueva
mosquitto_sub -h localhost -p 1883 -t "atabey/#"

# Debería mostrar SOLO:
# (cuando Vantroi envía datos)

atabey/ESP32-01/buffer {"device_id":"ESP32-01","buffer_id":"ESP32-01_20261101_143000_abc123",...}
atabey/ack/ESP32-01 {"type":"ack","device_id":"ESP32-01","accepted":6,"rejected":0,...}

# Si ves datos de múltiples sensores cada segundo = simulador activo
# Si ves datos cada 30 segundos en bursts = Vantroi enviando buffer ✓
```

### Dashboard - Verificar Datos en Tiempo Real

1. Abre http://localhost:5173
2. Ve a vista de Domo o Tripulante
3. Deberías ver:
   - ✓ Sin datos inicialmente (limpio)
   - ✓ Cuando Vantroi envía: datos nuevos cada 30 seg
   - ✓ Gráficos mostrando las lecturas

4. Si ves datos llegando cada segundo = hay un simulador activo

---

## ⚠️ Solución de Problemas

### "Veo datos pero no sé si son de Vantroi o del simulador"

Revisa el `device_id`:
```bash
# En terminal de MQTT
mosquitto_sub -h localhost -p 1883 -t "atabey/+/buffer" | jq '.device_id'

# Debería mostrar:
# "ESP32-01" (o lo que Vantroi configure)

# Si ves múltiples device_ids diferentes = hay simuladores
```

### "Datos aparecen cada segundo (muy frecuente)"

Hay un simulador activo:
```bash
# Busca procesos Python
Get-Process | Where-Object {$_.ProcessName -like "*python*"}

# Detén cualquier que no sea:
# - uvicorn (backend)
# - npm (frontend)
```

### "Datos solo aparecen de ciertos sensores"

Verifica que Vantroi esté enviando los sensores que configuró:
```bash
# Revisar qué sensores envió Vantroi
mosquitto_sub -h localhost -p 1883 -t "atabey/+/buffer" | jq '.readings[].sensor_id'

# Debería mostrar:
# "TEMP-01", "HUM-01", etc. (según lo que Vantroi configuró)
```

---

## 📝 Checklist Final Antes de que Vantroi Envíe

- [ ] Todos los simuladores están PARADOS (Ctrl+C)
- [ ] Backend está corriendo: `http://localhost:8000/health` → 200 OK
- [ ] Frontend está corriendo: `http://localhost:5173` → Dashboard carga
- [ ] MQTT está conectado: Backend logs muestran "Suscrito a atabey/#"
- [ ] Base de datos está limpia (0 lecturas históricas)
- [ ] `mosquitto_sub` muestra: NADA (esperando a Vantroi)
- [ ] Dashboard está vacío (esperando a Vantroi)

**¡Listo para recibir datos de Vantroi! 🚀**

---

## 🔄 Cuando Vantroi Envíe Datos

### Esperado:
1. ESP32 se conecta a WiFi
2. ESP32 se conecta a MQTT
3. Cada 30 segundos, ESP32 envía buffer:
   ```
   atabey/ESP32-01/buffer {...}
   ```
4. Backend recibe y confirma:
   ```
   atabey/ack/ESP32-01 {type: "ack", accepted: 6, ...}
   ```
5. Dashboard se actualiza en tiempo real ✓

### Si NO funciona:
1. Verifica que Vantroi tenga la IP/puerto MQTT correcto
2. Verifica WiFi en el ESP32
3. Revisa logs del backend: `backend/server.log`
4. Contacta a tu-usuario

---

## 📞 Contacto

Si tienes problemas:
1. Verifica este documento
2. Revisa logs del backend
3. Usa `mosquitto_sub` para monitorear MQTT
4. Contacta a tu-usuario con capturas de pantalla
