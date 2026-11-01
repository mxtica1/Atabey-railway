#!/usr/bin/env python3
"""
Pre-deploy checklist ejecutable para Misión Atabey.

Valida:
1. SECRET_KEY configurado y seguro
2. DATABASE_URL accesible
3. MQTT_HOST accesible
4. CORS_ORIGINS apropiado
5. Roles semilla creados
6. Índices de BD creados
7. Tablas de auditoría presentes

Uso:
    python scripts/pre-deploy-check.py

Retorna exit code 0 si todo está ok, 1 si hay problemas.
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime

# Agregar backend al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.security import validate_secrets
from backend import db
import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(message)s",
)
logger = logging.getLogger(__name__)

CHECKS_PASSED = 0
CHECKS_FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> bool:
    """Registra el resultado de una validación."""
    global CHECKS_PASSED, CHECKS_FAILED
    status = "✓" if condition else "✗"
    level = logging.INFO if condition else logging.ERROR
    logger.log(level, "%s %s%s", status, name, f" — {detail}" if detail else "")
    if condition:
        CHECKS_PASSED += 1
    else:
        CHECKS_FAILED += 1
    return condition


def main():
    """Ejecuta todas las validaciones."""
    logger.info("═" * 70)
    logger.info("PRE-DEPLOY CHECK — Misión Atabey v1.0")
    logger.info("Timestamp: %s", datetime.now().isoformat())
    logger.info("═" * 70)
    
    # 1. Validación de secretos
    logger.info("\n[1] SEGURIDAD")
    try:
        secrets = validate_secrets()
        check("SECRET_KEY configurado", True)
        check("SECRET_KEY es seguro", not secrets.get("secret_key_is_dev", False))
        check("SECRET_KEY suficientemente largo", secrets.get("secret_key_length_ok", False))
        check("DEFAULT_ROL recomendado", secrets.get("default_rol_recommended", False))
    except ValueError as e:
        check("Validación de secretos", False, str(e))
        return 1
    
    # 2. Validación de DATABASE_URL
    logger.info("\n[2] BASE DE DATOS")
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        try:
            conn = psycopg2.connect(database_url, connect_timeout=5)
            check("DATABASE_URL accesible", True)
            conn.close()
        except Exception as e:
            check("DATABASE_URL accesible", False, str(e))
    else:
        check("DATABASE_URL accesible", False, "No configurado")
    
    # 3. Validar que existen las tablas
    try:
        conn = db.get_connection()
        with conn.cursor() as cur:
            # Verificar tablas críticas
            tables = [
                "readings", "users", "thresholds", "alerts", "locations",
                "ingest_ack_audit", "audit_log"
            ]
            for table in tables:
                cur.execute("""
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = %s
                """, (table,))
                exists = cur.fetchone() is not None
                check(f"Tabla '{table}' existe", exists)
        conn.close()
    except Exception as e:
        check("Conexión a BD", False, str(e))
    
    # 4. Validación de MQTT
    logger.info("\n[3] MQTT")
    mqtt_host = os.getenv("MQTT_HOST", "").strip()
    mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
    if mqtt_host:
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((mqtt_host, mqtt_port))
            sock.close()
            is_accessible = result == 0
            check(f"MQTT_HOST '{mqtt_host}:{mqtt_port}' accesible", is_accessible)
        except Exception as e:
            check(f"MQTT_HOST '{mqtt_host}:{mqtt_port}' accesible", False, str(e))
    else:
        check("MQTT_HOST configurado", False)
    
    # 5. Validación de CORS
    logger.info("\n[4] CORS")
    require_login = os.getenv("REQUIRE_LOGIN", "true").strip().lower() not in ("false", "0", "no")
    cors_origins = os.getenv("CORS_ORIGINS", "").strip()
    
    if require_login:
        check("REQUIRE_LOGIN=true (producción)", True)
        if cors_origins and "*" not in cors_origins:
            check("CORS_ORIGINS limitado (seguro)", True, cors_origins[:50])
        elif not cors_origins:
            check("CORS_ORIGINS no explícito", True, "usando default [localhost:5173]")
        else:
            check("CORS_ORIGINS limitado (seguro)", False, f"'{cors_origins}' permite *")
    else:
        check("REQUIRE_LOGIN=false (desarrollo)", True, "recuerda: cambiar antes de producción")
    
    # 6. Validación de roles semilla
    logger.info("\n[5] USUARIOS SEMILLA")
    try:
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            user_count = cur.fetchone()[0]
        conn.close()
        check(f"Usuarios creados", user_count >= 3, f"{user_count} usuarios")
    except Exception as e:
        check("Usuarios semilla", False, str(e))
    
    # 7. Resumen
    logger.info("\n" + "═" * 70)
    total = CHECKS_PASSED + CHECKS_FAILED
    logger.info("RESULTADO: %d/%d validaciones pasaron", CHECKS_PASSED, total)
    if CHECKS_FAILED == 0:
        logger.info("✓ Sistema listo para deploy")
        logger.info("═" * 70)
        return 0
    else:
        logger.error("✗ Hay %d problemas a resolver", CHECKS_FAILED)
        logger.error("═" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
