# 🗑️ Cómo Limpiar la Base de Datos (Eliminar datos de prueba)

**Propósito:** Eliminar todas las lecturas y buffers de ingesta para dejar la BD limpia antes de que Vantroi envíe datos reales.

---

## 🔐 Autenticación Requerida

Solo los **administradores** pueden ejecutar este comando.

**Credenciales de prueba:**
- Usuario: `admin`
- Contraseña: `admin_pass`

---

## ✅ Opción 1: Usando Swagger UI (Visual)

1. Abre: `https://atabey-backend-k7kh.onrender.com/docs`
2. Click en **"Authorize"** (arriba a la derecha)
3. Usa credenciales:
   - Username: `admin`
   - Password: `admin_pass`
4. Busca endpoint: **DELETE /admin/data/readings**
5. Click en **"Try it out"** y luego **"Execute"**

**Respuesta esperada (HTTP 200):**
```json
{
  "status": "ok",
  "message": "Se eliminaron X lecturas",
  "readings_before": X,
  "readings_after": 0
}
```

---

## ✅ Opción 2: Usando curl (Terminal)

### Paso 1: Obtener token de autenticación

```bash
curl -X POST https://atabey-backend-k7kh.onrender.com/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin_pass"
```

Respuesta:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

Copia el `access_token`.

### Paso 2: Ejecutar DELETE con el token

```bash
curl -X DELETE https://atabey-backend-k7kh.onrender.com/admin/data/readings \
  -H "Authorization: Bearer <TU_TOKEN_AQUI>"
```

Respuesta:
```json
{
  "status": "ok",
  "message": "Se eliminaron 7 lecturas",
  "readings_before": 7,
  "readings_after": 0
}
```

---

## ⚠️ Advertencia

- **NO HAY UNDO**: Esta operación es irreversible
- Elimina **TODAS** las lecturas
- Se usa solo para limpiar datos de prueba
- Después de ejecutar, la BD está vacía y lista para Vantroi

---

## 📊 Verificación Posterior

Para confirmar que la BD está limpia:

1. Abre el dashboard: `https://atabey-frontend.onrender.com`
2. Pestaña "Ingesta" o "Domo"
3. No deberías ver datos viejos

---

## 🚀 Próximo Paso

Una vez que la BD esté limpia:
1. Vantroi comienza a enviar datos
2. Los datos aparecen **directamente** en el dashboard
3. Sin "ruido" de datos de prueba

