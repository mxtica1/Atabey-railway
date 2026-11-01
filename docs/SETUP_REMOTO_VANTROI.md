# 🌐 Setup Remoto - Recibir Datos de Vantroi desde Otra Ubicación

## El Problema

Vantroi está en **otra ubicación geográfica** (no en tu red local). Por lo tanto:
- ❌ No puede conectar a `localhost:8000`
- ❌ No puede conectar a IP privada (192.168.X.X)
- ✅ Necesita una **URL pública** que sea accesible desde internet

---

## Soluciones Disponibles

### Opción A: ngrok (MÁS FÁCIL - Recomendado para Desarrollo)

**Ventajas:**
- ✅ Setup en 2 minutos
- ✅ Gratuito
- ✅ No requiere configuración DNS
- ✅ Perfect para testing

**Desventajas:**
- ⚠️ URL cambia cada vez (free plan)
- ⚠️ Límite de ancho de banda (gratuito)

#### Pasos:

1. **Descargar ngrok:**
   ```bash
   # Ir a https://ngrok.com/download
   # Descargar para Windows
   # Descomprimir en una carpeta
   ```

2. **Autenticar (opcional pero recomendado):**
   ```bash
   ngrok config add-authtoken tu-token-de-ngrok
   # (Get token from ngrok dashboard after signing up)
   ```

3. **Crear túnel a puerto 8000:**
   ```bash
   ngrok http 8000
   ```

4. **Copiar la URL pública:**
   ```
   Forwarding  https://xxxx-xxxx-xxxx.ngrok.io -> http://localhost:8000
   ```

5. **Darle a Vantroi la URL:**
   ```
   MQTT Server: xxxx-xxxx-xxxx.ngrok.io
   Puerto: 443 (MQTT sobre HTTPS, ngrok lo maneja automáticamente)
   ```

**Nota:** La URL cambia cada tiempo. Si necesitas permanente, usa plan pagado.

---

### Opción B: CloudFlare Tunnel (Gratuito, Permanente)

**Ventajas:**
- ✅ URL permanente
- ✅ Totalmente gratuito
- ✅ Buena infraestructura
- ✅ Manejo de DNS

**Desventajas:**
- ⚠️ Setup más complejo (~10 min)
- ⚠️ Requiere cuenta CloudFlare

#### Pasos:

1. **Instalar CloudFlare CLI:**
   ```bash
   # Descargar cloudflared desde:
   # https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/
   
   # O con Chocolatey:
   choco install cloudflare-warp
   ```

2. **Autenticar:**
   ```bash
   cloudflared tunnel login
   # Se abre navegador para autenticar con CloudFlare
   ```

3. **Crear túnel:**
   ```bash
   cloudflared tunnel create atabey-production
   ```

4. **Configurar DNS (si tienes dominio):**
   ```bash
   cloudflared tunnel route dns atabey-production atabey.tu-dominio.com
   ```

5. **Correr el túnel:**
   ```bash
   cloudflared tunnel run atabey-production
   ```

6. **URL pública:**
   ```
   https://atabey.tu-dominio.com (o la que configures)
   ```

---

### Opción C: Deploy en VPS/PaaS

Dejar la aplicación corriendo 24/7 en:
- Railway.app
- Render.com
- Fly.io
- DigitalOcean

**Ventajas:**
- ✅ Production-ready
- ✅ URL permanente
- ✅ Dominio personalizado

**Desventajas:**
- ⚠️ Costo ($5-10/mes típicamente)
- ⚠️ Setup más complejo

---

## Solución Rápida: ngrok

### Setup en 3 minutos:

```bash
# 1. Descargar ngrok
# https://ngrok.com/download

# 2. En PowerShell, ir a carpeta de ngrok
cd C:\ruta\a\ngrok

# 3. Crear túnel
.\ngrok http 8000

# 4. Ver output:
# Forwarding  https://abc123-xyz789.ngrok.io -> http://localhost:8000

# 5. Darle a Vantroi:
# MQTT_SERVER = abc123-xyz789.ngrok.io
# MQTT_PORT = 443
```

**¡Listo! Vantroi puede enviar datos desde cualquier parte del mundo.**

---

## Configurar Vantroi para URL Remota

### En código Arduino de Vantroi:

```cpp
// Si usas ngrok:
const char* MQTT_SERVER = "abc123-xyz789.ngrok.io";  // Sin https://
const int MQTT_PORT = 443;  // Puerto HTTPS

// Si usas CloudFlare:
const char* MQTT_SERVER = "atabey.tu-dominio.com";
const int MQTT_PORT = 443;

// En ambos casos, el cliente MQTT se comunicará sobre HTTPS
```

**Nota:** Algunos brokers MQTT en la nube soportan TLS. Vantroi debe usar librería con soporte TLS:
```cpp
#include <WiFiClientSecure.h>
// En lugar de WiFiClient
```

---

## Alternativa Más Simple: Cambiar MQTT_PORT

Si ngrok no soporta TLS en plan gratuito, usa puerto HTTP:

```cpp
const char* MQTT_SERVER = "abc123-xyz789.ngrok.io";
const int MQTT_PORT = 80;  // HTTP (menos seguro, solo para desarrollo)
```

---

## Verificar que Funciona

### 1. Backend sigue corriendo en localhost:8000
```bash
curl http://localhost:8000/health
→ 200 OK
```

### 2. ngrok túnel abierto
```bash
# En terminal ngrok:
Forwarding  https://abc123-xyz789.ngrok.io -> http://localhost:8000
```

### 3. Verificar desde fuera
```bash
curl https://abc123-xyz789.ngrok.io/health
→ 200 OK (desde cualquier lugar del mundo)
```

### 4. Vantroi conecta
```
Arduino Serial Monitor:
✓ WiFi conectado
✓ MQTT conectado a abc123-xyz789.ngrok.io:443
✓ Escuchando ACKs
```

### 5. Ver datos en MQTT
```bash
mosquitto_sub -h abc123-xyz789.ngrok.io -p 443 -t "atabey/#"

# O localmente:
mosquitto_sub -h localhost -p 1883 -t "atabey/#"

# Deberías ver:
atabey/ESP32-VANTROI/buffer {...}
atabey/ack/ESP32-VANTROI {...}
```

### 6. Dashboard muestra datos
```
http://localhost:5173
→ Datos nuevos cada 30 segundos ✓
```

---

## Mantener Túnel Abierto Permanentemente

### ngrok:
```bash
# Para desarrollo rápido, mantén terminal abierta con:
.\ngrok http 8000

# Si necesitas URL permanente, upgrade a plan pagado
```

### CloudFlare:
```bash
# Crear servicio que corra en background

# Opción 1: Task Scheduler (Windows)
# Crear tarea que ejecute: cloudflared tunnel run atabey-production
# Configurar para que inicie con Windows

# Opción 2: NSSM (Non-Sucking Service Manager)
# nssm install atabey-tunnel cloudflared tunnel run atabey-production
# nssm start atabey-tunnel
```

---

## Seguridad

### ⚠️ Advertencia para Desarrollo:
- ngrok (plan gratuito) NO usa TLS por defecto
- Datos viajan sin encriptación
- **Solo para desarrollo/testing**

### ✅ Para Producción:
- Usa CloudFlare Tunnel (con TLS)
- O deploy en VPS con SSL/TLS
- Configura autenticación MQTT
- Usa SECRET_KEY fuerte en backend

---

## Ejemplo Completo: ngrok + Vantroi

### Terminal 1: Backend (ya corriendo)
```bash
cd C:\Users\UserGPC\Documents\Github\Local\Atabey
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 2: ngrok
```bash
cd C:\path\to\ngrok
.\ngrok http 8000

# Output:
# Forwarding  https://myid-12345.ngrok.io -> http://localhost:8000
```

### Terminal 3: Monitorear MQTT
```bash
# En máquina con Atabey instalado:
mosquitto_sub -h localhost -p 1883 -t "atabey/#"

# Verás datos llegando cuando Vantroi envíe
```

### Configuración de Vantroi:
```cpp
const char* MQTT_SERVER = "myid-12345.ngrok.io";
const int MQTT_PORT = 80;  // O 443 si soporta TLS
```

**Resultado:** Vantroi envía desde su casa → ngrok → Tu Backend → PostgreSQL → Dashboard ✓

---

## Troubleshooting

| Problema | Solución |
|----------|----------|
| "Conexión rechazada" | Verifica que ngrok esté corriendo y mostrando URL |
| "URL no encontrada" | Copia URL correcta del terminal de ngrok |
| "MQTT connection timeout" | Verifica puerto (80 vs 443) |
| "Datos no llegan al dashboard" | Verifica que backend esté corriendo en localhost:8000 |
| "ngrok cambió URL" | Usa CloudFlare para URL permanente o plan pagado |

---

## Próximos Pasos

1. **Elige opción:** ngrok (rápido) o CloudFlare (permanente)
2. **Setup túnel:** Sigue pasos arriba
3. **Copiar URL pública:** Dale a Vantroi
4. **Vantroi conecta:** Arduino entra en setup
5. **Datos fluyen:** Backend recibe, dashboard muestra ✓

---

## Resumen

**Para recibir datos de Vantroi desde otra ubicación:**

```
Vantroi (casa, IP pública)
    ↓ WiFi + MQTT
    ↓ MQTT_SERVER = tu-url-publica.ngrok.io
    ↓
ngrok Tunnel
    ↓ Redirige a
    ↓
Backend FastAPI (localhost:8000)
    ↓
PostgreSQL
    ↓
Dashboard (http://localhost:5173)
    ↓
Datos en tiempo real ✓
```

**URL Pública = Clave para que Vantroi te envíe datos desde lejos** 🚀
