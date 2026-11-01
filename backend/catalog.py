"""
Catalogo canonico de variables de sensores — Mision Atabey.

ESTE ARCHIVO ES LA FUENTE DE VERDAD para:
  - que variables puede enviar el ESP32 / el firmware,
  - como se llama cada variable dentro de un "buffer de datos",
  - que unidades y umbrales usa cada una.

Se expone por HTTP en `GET /sensors/catalog` y se documenta en
`docs/SENSORS_CATALOG.md` + `docs/sensors-catalog.json` para que el agente
de integracion (Vantroi) pueda armar buffers validos sin leer codigo.

REGLA DEL CONTRATO (AGENTS.md — no modificar sin acuerdo del equipo de hardware):
    Cada lectura sigue esta estructura EXACTA:
    {
      "device_id": "ESP32-01",
      "sensor_id": "TEMP-01",
      "timestamp": "2026-09-24T20:15:00Z",
      "value": 28.4,
      "unit": "C",
      "sequence": 1542
    }

    `sequence` es un contador incremental POR SENSOR, para detectar lecturas
    perdidas. Un buffer son N lecturas con esa misma estructura.
"""

from typing import Optional

# ─── Grupos ──────────────────────────────────────────────────────────────────

GROUP_DOMO_AMBIENTAL = "domo_ambiental"
GROUP_DOMO_SUELO = "domo_suelo"
GROUP_BIO = "bio"
GROUP_EVA = "eva"
GROUP_IMU = "imu"

# ─── Dispositivos ────────────────────────────────────────────────────────────

DEVICE_DOMO = "ESP32-01"
DEVICE_TRIPULANTE = "EVA-01"

# ─── Catalogo ────────────────────────────────────────────────────────────────
#
# Cada entrada:
#   sensor_id   clave del contrato (identificador unico del sensor)
#   variable    nombre de la variable tal como debe aparecer en el buffer
#   nombre      nombre humano en espanol (UI / catalogo)
#   unit        unidad del valor (contrato)
#   group       agrupacion para el dashboard
#   description que mide
#   hardware    sensor fisico de referencia ("simulado" si no hay)
#   biometrico  True = requiere acceso restringido por rol
#   value_min   rango minimo de la simulacion
#   value_max   rango maximo de la simulacion
#   threshold   umbral de alerta (valor_min, valor_max) o None

CATALOG: list[dict] = [
    # ── Domo ambiental ──────────────────────────────────────────────────────
    {
        "sensor_id": "TEMP-01",
        "variable": "temperatura_aire",
        "nombre": "Temperatura del Aire",
        "unit": "C",
        "group": GROUP_DOMO_AMBIENTAL,
        "description": "Temperatura ambiental de la planta dentro del domo",
        "hardware": "DS18B20 / TMP117 (confirmar con equipo de hardware)",
        "biometrico": False,
        "value_min": 15.0,
        "value_max": 35.0,
        "threshold": (15.0, 35.0),
        "device_id": DEVICE_DOMO,
    },
    {
        "sensor_id": "HUM-01",
        "variable": "humedad_aire",
        "nombre": "Humedad del Aire",
        "unit": "%",
        "group": GROUP_DOMO_AMBIENTAL,
        "description": "Humedad relativa del aire dentro del domo",
        "hardware": "DHT22 / SHT31 (confirmar con equipo de hardware)",
        "biometrico": False,
        "value_min": 40.0,
        "value_max": 85.0,
        "threshold": (40.0, 85.0),
        "device_id": DEVICE_DOMO,
    },
    {
        "sensor_id": "CO2-01",
        "variable": "concentracion_co2",
        "nombre": "Concentracion de Gas (CO2)",
        "unit": "ppm",
        "group": GROUP_DOMO_AMBIENTAL,
        "description": "Concentracion de CO2 / calidad del aire del domo",
        "hardware": "MH-Z19 (confirmar con equipo de hardware)",
        "biometrico": False,
        "value_min": 400.0,
        "value_max": 1200.0,
        "threshold": (400.0, 1200.0),
        "device_id": DEVICE_DOMO,
    },
    {
        "sensor_id": "LUX-01",
        "variable": "luz_ambiental",
        "nombre": "Iluminacion (lux)",
        "unit": "lux",
        "group": GROUP_DOMO_AMBIENTAL,
        "description": "Luz visible + infrarrojo. NO es indice UV.",
        "hardware": "TSL2591",
        "biometrico": False,
        "value_min": 100.0,
        "value_max": 3000.0,
        "threshold": (100.0, 3000.0),
        "device_id": DEVICE_DOMO,
    },

    # ── Domo: suelo (STEMMA Soil = humedad + temperatura fisica conjunta) ──
    {
        "sensor_id": "SOIL-HUM-01",
        "variable": "humedad_suelo_1",
        "nombre": "Humedad del Suelo S1",
        "unit": "%",
        "group": GROUP_DOMO_SUELO,
        "description": "Humedad del suelo en la zona 1",
        "hardware": "STEMMA Soil Sensor",
        "biometrico": False,
        "value_min": 20.0,
        "value_max": 70.0,
        "threshold": (20.0, 70.0),
        "device_id": DEVICE_DOMO,
    },
    {
        "sensor_id": "SOIL-HUM-02",
        "variable": "humedad_suelo_2",
        "nombre": "Humedad del Suelo S2",
        "unit": "%",
        "group": GROUP_DOMO_SUELO,
        "description": "Humedad del suelo en la zona 2",
        "hardware": "STEMMA Soil Sensor",
        "biometrico": False,
        "value_min": 20.0,
        "value_max": 70.0,
        "threshold": (20.0, 70.0),
        "device_id": DEVICE_DOMO,
    },
    {
        "sensor_id": "SOIL-HUM-03",
        "variable": "humedad_suelo_3",
        "nombre": "Humedad del Suelo S3",
        "unit": "%",
        "group": GROUP_DOMO_SUELO,
        "description": "Humedad del suelo en la zona 3",
        "hardware": "STEMMA Soil Sensor",
        "biometrico": False,
        "value_min": 20.0,
        "value_max": 70.0,
        "threshold": (20.0, 70.0),
        "device_id": DEVICE_DOMO,
    },
    {
        "sensor_id": "SOIL-TEMP-01",
        "variable": "temperatura_suelo_1",
        "nombre": "Temperatura del Suelo S1",
        "unit": "C",
        "group": GROUP_DOMO_SUELO,
        "description": "Temperatura del suelo en la zona 1 (misma lectura fisica que SOIL-HUM-01)",
        "hardware": "STEMMA Soil Sensor",
        "biometrico": False,
        "value_min": 15.0,
        "value_max": 30.0,
        "threshold": (15.0, 30.0),
        "device_id": DEVICE_DOMO,
    },
    {
        "sensor_id": "SOIL-TEMP-02",
        "variable": "temperatura_suelo_2",
        "nombre": "Temperatura del Suelo S2",
        "unit": "C",
        "group": GROUP_DOMO_SUELO,
        "description": "Temperatura del suelo en la zona 2 (misma lectura fisica que SOIL-HUM-02)",
        "hardware": "STEMMA Soil Sensor",
        "biometrico": False,
        "value_min": 15.0,
        "value_max": 30.0,
        "threshold": (15.0, 30.0),
        "device_id": DEVICE_DOMO,
    },
    {
        "sensor_id": "SOIL-TEMP-03",
        "variable": "temperatura_suelo_3",
        "nombre": "Temperatura del Suelo S3",
        "unit": "C",
        "group": GROUP_DOMO_SUELO,
        "description": "Temperatura del suelo en la zona 3 (misma lectura fisica que SOIL-HUM-03)",
        "hardware": "STEMMA Soil Sensor",
        "biometrico": False,
        "value_min": 15.0,
        "value_max": 30.0,
        "threshold": (15.0, 30.0),
        "device_id": DEVICE_DOMO,
    },

    # ── Domo: nutrientes (SIMULADOS — sin sensor fisico documentado) ────────
    {
        "sensor_id": "NPK-N-01",
        "variable": "nitrogeno_suelo",
        "nombre": "Nitrogeno (N)",
        "unit": "mg/kg",
        "group": GROUP_DOMO_SUELO,
        "description": "Nitrogeno disponible en el suelo — SIMULADO, sin sensor fisico",
        "hardware": "simulado",
        "biometrico": False,
        "value_min": 50.0,
        "value_max": 300.0,
        "threshold": (50.0, 300.0),
        "device_id": DEVICE_DOMO,
    },
    {
        "sensor_id": "NPK-P-01",
        "variable": "fosforo_suelo",
        "nombre": "Fosforo (P)",
        "unit": "mg/kg",
        "group": GROUP_DOMO_SUELO,
        "description": "Fosforo disponible en el suelo — SIMULADO, sin sensor fisico",
        "hardware": "simulado",
        "biometrico": False,
        "value_min": 20.0,
        "value_max": 150.0,
        "threshold": (20.0, 150.0),
        "device_id": DEVICE_DOMO,
    },
    {
        "sensor_id": "NPK-K-01",
        "variable": "potasio_suelo",
        "nombre": "Potasio (K)",
        "unit": "mg/kg",
        "group": GROUP_DOMO_SUELO,
        "description": "Potasio disponible en el suelo — SIMULADO, sin sensor fisico",
        "hardware": "simulado",
        "biometrico": False,
        "value_min": 100.0,
        "value_max": 400.0,
        "threshold": (100.0, 400.0),
        "device_id": DEVICE_DOMO,
    },

    # ── Tripulante: biometricos (acceso restringido) ────────────────────────
    {
        "sensor_id": "HR-01",
        "variable": "pulso_cardiaco",
        "nombre": "Pulso Cardiaco",
        "unit": "bpm",
        "group": GROUP_BIO,
        "description": "Frecuencia cardiaca del tripulante",
        "hardware": "MAX30102 / sensor de pulso (confirmar)",
        "biometrico": True,
        "value_min": 55.0,
        "value_max": 140.0,
        "threshold": (55.0, 140.0),
        "device_id": DEVICE_TRIPULANTE,
    },
    {
        "sensor_id": "SPO2-01",
        "variable": "saturacion_oxigeno",
        "nombre": "Saturacion de Oxigeno (SpO2)",
        "unit": "%",
        "group": GROUP_BIO,
        "description": "Saturacion de oxigeno en sangre",
        "hardware": "MAX30102 (confirmar)",
        "biometrico": True,
        "value_min": 92.0,
        "value_max": 100.0,
        "threshold": (92.0, 100.0),
        "device_id": DEVICE_TRIPULANTE,
    },
    {
        "sensor_id": "BTEMP-01",
        "variable": "temperatura_corporal",
        "nombre": "Temperatura Corporal",
        "unit": "C",
        "group": GROUP_BIO,
        "description": "Temperatura corporal del tripulante",
        "hardware": "sensor de temperatura corporal (confirmar)",
        "biometrico": True,
        "value_min": 34.5,
        "value_max": 37.5,
        "threshold": (34.5, 37.5),
        "device_id": DEVICE_TRIPULANTE,
    },

    # ── Tripulante: soporte de vida (mochila EVA) ──────────────────────────
    {
        "sensor_id": "EVA-TEMP-01",
        "variable": "temperatura_traje",
        "nombre": "Temperatura del Traje",
        "unit": "C",
        "group": GROUP_EVA,
        "description": "Temperatura dentro del traje de soporte de vida",
        "hardware": "DS18B20 / TMP117 (confirmar)",
        "biometrico": False,
        "value_min": 15.0,
        "value_max": 35.0,
        "threshold": (15.0, 35.0),
        "device_id": DEVICE_TRIPULANTE,
    },
    {
        "sensor_id": "EVA-HUM-01",
        "variable": "humedad_traje",
        "nombre": "Humedad del Traje",
        "unit": "%",
        "group": GROUP_EVA,
        "description": "Humedad dentro del traje de soporte de vida",
        "hardware": "DHT22 / SHT31 (confirmar)",
        "biometrico": False,
        "value_min": 30.0,
        "value_max": 70.0,
        "threshold": (30.0, 70.0),
        "device_id": DEVICE_TRIPULANTE,
    },
    {
        "sensor_id": "EVA-PRESS-01",
        "variable": "presion_traje",
        "nombre": "Presion del Traje",
        "unit": "hPa",
        "group": GROUP_EVA,
        "description": "Presion atmosferica dentro de la mochila EVA",
        "hardware": "BMP280 / MS5611 (confirmar)",
        "biometrico": False,
        "value_min": 950.0,
        "value_max": 1030.0,
        "threshold": (950.0, 1030.0),
        "device_id": DEVICE_TRIPULANTE,
    },

    # ── Tripulante: IMU (BNO055 — solo aceleracion lineal en este corte) ───
    {
        "sensor_id": "ACC-X-01",
        "variable": "aceleracion_x",
        "nombre": "Aceleracion X",
        "unit": "m/s²",
        "group": GROUP_IMU,
        "description": "Aceleracion lineal en eje X (BNO055 compensada)",
        "hardware": "BNO055",
        "biometrico": False,
        "value_min": -3.0,
        "value_max": 3.0,
        "threshold": None,
        "device_id": DEVICE_TRIPULANTE,
    },
    {
        "sensor_id": "ACC-Y-01",
        "variable": "aceleracion_y",
        "nombre": "Aceleracion Y",
        "unit": "m/s²",
        "group": GROUP_IMU,
        "description": "Aceleracion lineal en eje Y (BNO055 compensada)",
        "hardware": "BNO055",
        "biometrico": False,
        "value_min": -3.0,
        "value_max": 3.0,
        "threshold": None,
        "device_id": DEVICE_TRIPULANTE,
    },
    {
        "sensor_id": "ACC-Z-01",
        "variable": "aceleracion_z",
        "nombre": "Aceleracion Z",
        "unit": "m/s²",
        "group": GROUP_IMU,
        "description": "Aceleracion lineal en eje Z (BNO055 compensada)",
        "hardware": "BNO055",
        "biometrico": False,
        "value_min": -3.0,
        "value_max": 3.0,
        "threshold": None,
        "device_id": DEVICE_TRIPULANTE,
    },
    {
        "sensor_id": "ACTIVITY-01",
        "variable": "actividad",
        "nombre": "Estado de Actividad",
        "unit": "código",
        "group": GROUP_IMU,
        "description": "Estado de actividad del BNO055 (0=Still, 1=Walking, 2=Running, 3=Tilting)",
        "hardware": "BNO055",
        "biometrico": False,
        "value_min": 0,
        "value_max": 3,
        "threshold": None,
        "device_id": DEVICE_TRIPULANTE,
    },
]

# ─── Indices para busqueda rapida ────────────────────────────────────────────

BY_SENSOR_ID: dict[str, dict] = {entry["sensor_id"]: entry for entry in CATALOG}
BY_VARIABLE: dict[str, dict] = {entry["variable"]: entry for entry in CATALOG}

BIOMETRIC_SENSOR_IDS: frozenset[str] = frozenset(
    entry["sensor_id"] for entry in CATALOG if entry["biometrico"]
)

# ─── API publica ─────────────────────────────────────────────────────────────

def catalog_as_dicts() -> list[dict]:
    """Catalogo en forma de diccionarios JSON-serializables."""
    out = []
    for entry in CATALOG:
        item = dict(entry)
        threshold = item.get("threshold")
        item["threshold"] = (
            {"valor_min": threshold[0], "valor_max": threshold[1]} if threshold else None
        )
        out.append(item)
    return out


def catalog_summary() -> dict:
    """Resumen compacto: agrupado por dispositivo."""
    devices: dict[str, dict] = {}
    for entry in CATALOG:
        device_id = entry["device_id"]
        bucket = devices.setdefault(device_id, {
            "device_id": device_id,
            "sensor_count": 0,
            "groups": [],
            "sensors": [],
        })
        bucket["sensor_count"] += 1
        if entry["group"] not in bucket["groups"]:
            bucket["groups"].append(entry["group"])
        bucket["sensors"].append({
            "sensor_id": entry["sensor_id"],
            "variable": entry["variable"],
            "nombre": entry["nombre"],
            "unit": entry["unit"],
            "group": entry["group"],
            "description": entry["description"],
            "hardware": entry["hardware"],
            "biometrico": entry["biometrico"],
            "value_min": entry["value_min"],
            "value_max": entry["value_max"],
            "device_id": device_id,
            "threshold": (
                {"valor_min": entry["threshold"][0], "valor_max": entry["threshold"][1]}
                if entry["threshold"] else None
            ),
        })
    return {
        "total_sensors": len(CATALOG),
        "biometric_sensors": sorted(BIOMETRIC_SENSOR_IDS),
        "devices": list(devices.values()),
        "contract": {
            "reading": {
                "device_id": "string",
                "sensor_id": "string",
                "timestamp": "ISO-8601 UTC",
                "value": "number",
                "unit": "string",
                "sequence": "int (incremental por sensor)",
            },
            "buffer": {
                "device_id": "string",
                "buffer_id": "string unico del envio",
                "sent_at": "ISO-8601 UTC",
                "readings": "array de readings (contrato de arriba)",
            },
            "ack": {
                "type": "ack",
                "device_id": "string",
                "buffer_id": "string",
                "received_at": "ISO-8601 UTC",
                "accepted": "int",
                "rejected": "int",
                "items": "array de {sensor_id, sequence, status, received_at, db_id, error?}",
            },
            "mqtt": {
                "buffer_topic": "atabey/{device_id}/buffer",
                "ack_topic": "atabey/ack/{device_id}",
                "reading_topic": "atabey/{group}/{sensor_id}",
            },
        },
    }


def lookup(sensor_id: str) -> Optional[dict]:
    return BY_SENSOR_ID.get(sensor_id)
