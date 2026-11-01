# Schema de Base de Datos — Misión Atabey

## ER Diagram Completo

```
┌─────────────────────────────────────────────────────────────────┐
│                         LECTURA DE DATOS                        │
├─────────────────────────────────────────────────────────────────┤
│ readings                                                        │
│  ├── id (SERIAL PRIMARY KEY)                                    │
│  ├── device_id (TEXT NOT NULL)         — "ESP32-01"             │
│  ├── sensor_id (TEXT NOT NULL)         — "TEMP-01"              │
│  ├── timestamp (TIMESTAMPTZ NOT NULL)  — medición del sensor    │
│  ├── value (DOUBLE PRECISION NOT NULL) — 28.4                   │
│  ├── unit (TEXT NOT NULL)              — "C"                    │
│  ├── sequence (INTEGER NOT NULL)       — contador incremental   │
│  ├── received_at (TIMESTAMPTZ)         — cuando llegó al srvr   │
│  └── buffer_id (TEXT)                  — para auditoría         │
│      Índices:                                                    │
│      ├── (sensor_id, timestamp DESC)                            │
│      └── (buffer_id)                                            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      POSICIÓN TRIPULANTE                        │
├─────────────────────────────────────────────────────────────────┤
│ locations                                                       │
│  ├── id (SERIAL PRIMARY KEY)                                    │
│  ├── device_id (TEXT NOT NULL)         — "EVA-01"               │
│  ├── timestamp (TIMESTAMPTZ NOT NULL)  — del GPS                │
│  ├── lat (DOUBLE PRECISION NOT NULL)   — latitud                │
│  ├── lon (DOUBLE PRECISION NOT NULL)   — longitud               │
│  ├── sequence (INTEGER NOT NULL)       — contador               │
│  └── sexo (TEXT CHECK 'M','F',NULL)   — para color mapa        │
│      Índice: (device_id, timestamp DESC)                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      CONFIGURACIÓN & CONTROL                    │
├─────────────────────────────────────────────────────────────────┤
│ thresholds                                                      │
│  ├── sensor_id (TEXT PRIMARY KEY)      — "TEMP-01"              │
│  ├── valor_min (DOUBLE PRECISION)      — 15.0                   │
│  ├── valor_max (DOUBLE PRECISION)      — 35.0                   │
│  ├── actualizado_por (TEXT)            — usuario que cambió     │
│  └── actualizado_en (TIMESTAMPTZ)      — cuándo                 │
│                                                                  │
│ alerts                                                          │
│  ├── id (SERIAL PRIMARY KEY)                                    │
│  ├── sensor_id (TEXT NOT NULL)                                  │
│  ├── value (DOUBLE PRECISION)          — valor que excedió      │
│  ├── threshold_excedido (TEXT)         — "min" o "max"          │
│  ├── valor_min, valor_max (DOUBLE)     — umbrales cuando pasó   │
│  ├── timestamp (TIMESTAMPTZ)           — del sensor             │
│  ├── severidad (TEXT)                  — "critico" o "advertencia"
│  ├── resuelto (BOOLEAN DEFAULT FALSE)                           │
│  ├── visto_por_ultima_vez (TIMESTAMPTZ)— última actualización   │
│  ├── resuelto_en (TIMESTAMPTZ)         — cuándo se resolvió     │
│  └── resuelto_por (TEXT)               — usuario que resolvió   │
│      Índices:                                                    │
│      ├── (sensor_id, timestamp DESC)                            │
│      ├── (resuelto=FALSE)                                       │
│      └── (sensor_id, threshold_excedido, resuelto=FALSE)        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    AUTENTICACIÓN & AUTORIZACIÓN                 │
├─────────────────────────────────────────────────────────────────┤
│ users                                                           │
│  ├── id (SERIAL PRIMARY KEY)                                    │
│  ├── username (TEXT UNIQUE NOT NULL)   — "admin"                │
│  ├── password_hash (TEXT NOT NULL)     — bcrypt                 │
│  └── rol (TEXT CHECK 'administrador'   — roles semilla:         │
│          |'control_mision'                                      │
│          |'observador')                                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        AUDITORÍA & TRAZABILIDAD                 │
├─────────────────────────────────────────────────────────────────┤
│ ingest_ack_audit                                                │
│  ├── id (SERIAL PRIMARY KEY)                                    │
│  ├── device_id (TEXT NOT NULL)         — "ESP32-01"             │
│  ├── buffer_id (TEXT UNIQUE NOT NULL)  — "buf-0001"             │
│  ├── received_at (TIMESTAMPTZ)         — cuándo llegó           │
│  ├── total_items (INTEGER)             — lecturas en buffer     │
│  ├── accepted (INTEGER)                — guardadas              │
│  ├── rejected (INTEGER)                — rechazadas             │
│  └── duplicates (INTEGER)              — duplicadas             │
│      Índice: (device_id, received_at DESC)                      │
│                                                                  │
│ audit_log                                                       │
│  ├── id (SERIAL PRIMARY KEY)                                    │
│  ├── entity (TEXT)                     — "umbral", "alerta"     │
│  ├── action (TEXT)                     — "create", "update"     │
│  ├── entity_id (TEXT)                  — "TEMP-01", "alert-5"   │
│  ├── old_value (TEXT)                  — JSON anterior          │
│  ├── new_value (TEXT)                  — JSON nuevo             │
│  ├── changed_by (TEXT)                 — usuario que cambió     │
│  └── changed_at (TIMESTAMPTZ)          — cuándo                 │
│      Índices:                                                    │
│      ├── (entity, changed_at DESC)                              │
│      └── (entity_id)                                            │
└─────────────────────────────────────────────────────────────────┘
```

## Volumen de Datos Estimado

| Tabla | Crecimiento | Retención | Índices |
|-------|-------------|-----------|---------|
| readings | ~50 registros/min (23 sensores × ~2 lecturas/min) | Histórico completo (nunca se borra) | 2 (rápido histórico) |
| locations | ~2 registros/min (1 tripulante × 2 por min) | Histórico completo | 1 |
| alerts | ~1-5 por evento | Histórico completo (resueltas o activas) | 3 (búsqueda rápida) |
| ingest_ack_audit | ~1 por buffer recibido (~6/min) | Histórico completo | 1 |
| audit_log | ~1 por cambio de config | Histórico completo | 2 |
| users, thresholds | Estático (˂50 registros) | Permanente | 0-1 |

**Estimado para 1 año de misión (24/7 datos)**:
- readings: ~26M registros (~2.6 GB)
- locations: ~1M registros (~100 MB)
- audit_log: ~10k registros (~10 MB)

## Migraciones

Todas las tablas se crean automáticamente en el startup:

```python
# backend/db.py
db.create_table()  # Ejecutado en backend/main.py lifespan()
```

**No hay Alembic ni migrations separadas**: el schema se versionea junto al código fuente. Cambios en `backend/db.py` → ALTER TABLE automático en producción.

**Convención**:
- Nuevas columnas: usar `DO $$` + `IF NOT EXISTS` para agregar sin fallar
- Índices: crear con `CREATE INDEX IF NOT EXISTS`
- Nunca dropear columnas (mantener backward-compatibility)

## Relaciones y Constraints

| Relación | Tipo | Nota |
|----------|------|------|
| readings.sensor_id → thresholds.sensor_id | FK lógica | Soft FK (no constraint, permite flexibilidad) |
| alerts.sensor_id → readings.sensor_id | FK lógica | Soft FK |
| audit_log.changed_by → users.username | FK lógica | Soft FK (puede ser NULL para auto-events) |
| readings.device_id | Patrón | "ESP32-01", "EVA-01", etc. (validado en código) |
| readings.buffer_id | UNIQUE | Previene duplicados en ingest |

## Performance Tips

1. **Queries frecuentes**:
   - Última lectura por sensor: `SELECT * FROM readings WHERE sensor_id=? ORDER BY timestamp DESC LIMIT 1`
   - Alertas activas: `SELECT * FROM alerts WHERE resuelto=FALSE ORDER BY timestamp DESC`
   - Histórico de 24h: `WHERE timestamp > NOW() - INTERVAL '24 hours'`

2. **Vacuum & Analyze** (mensual en producción):
   ```sql
   VACUUM ANALYZE;
   ```

3. **Partitioning** (si excedes 10GB): particionar `readings` por mes

4. **Backup**: PostgreSQL binary backup cada 6 horas

## Auditoría Completa

Gracias a `ingest_ack_audit` y `audit_log`, puedes:
- ✓ Rastrear cada buffer recibido (cuándo, de quién, cuántas lecturas)
- ✓ Detectar pérdida de datos (comparar sequence counter)
- ✓ Ver historial de cambios de configuración (quién cambió umbrales, cuándo)
- ✓ Resolver incidentes: "¿por qué se disparó una alerta a las 14:23?"
