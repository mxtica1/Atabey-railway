"""
Módulo de seguridad: rate limiting, validación de secretos, health checks.
"""
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# ── Rate Limiting ────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)


def get_limiter() -> Limiter:
    """Factory para obtener la instancia del limiter."""
    return limiter


async def rate_limit_exception_handler(request, exc: RateLimitExceeded):
    """Handler personalizado para excepciones de rate limit."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": "Too many requests. Please try again later.",
            "retry_after": 60,
        },
    )


# ── Validación de Secretos ───────────────────────────────────────────────────

def validate_secrets() -> dict[str, bool]:
    """
    Valida la configuración de seguridad al arrancar.
    
    Retorna dict con las validaciones y levanta excepción si hay problemas críticos.
    """
    results = {}
    secret_key = os.getenv("SECRET_KEY", "").strip()
    require_login = os.getenv("REQUIRE_LOGIN", "true").strip().lower() not in ("false", "0", "no")
    
    # Validar SECRET_KEY
    if not secret_key:
        logger.error("SECRET_KEY no configurado. Es requerido.")
        raise ValueError("SECRET_KEY no configurado")
    
    if secret_key in ("supersecretkey_for_dev_only", "dev", "secret", "changeme"):
        logger.warning("⚠ SECRET_KEY contiene valor de desarrollo: %s", secret_key)
        results["secret_key_is_dev"] = True
        if require_login:
            logger.error("❌ REQUIRE_LOGIN=true pero SECRET_KEY es de desarrollo. No es seguro.")
            raise ValueError("SECRET_KEY de desarrollo con REQUIRE_LOGIN=true. Abortando.")
    else:
        results["secret_key_is_dev"] = False
    
    if len(secret_key) < 32:
        logger.warning("⚠ SECRET_KEY muy corto (%d chars). Usar al menos 32.", len(secret_key))
        results["secret_key_length_ok"] = False
    else:
        results["secret_key_length_ok"] = True
    
    # Validar REQUIRE_LOGIN y DEFAULT_ROL
    default_rol = os.getenv("DEFAULT_ROL", "administrador").strip()
    if not require_login and default_rol != "observador":
        logger.warning(
            "⚠ REQUIRE_LOGIN=false pero DEFAULT_ROL=%s. "
            "Recomendado DEFAULT_ROL=observador para restringir biométricos.",
            default_rol
        )
        results["default_rol_recommended"] = False
    else:
        results["default_rol_recommended"] = True
    
    # Validar DATABASE_URL
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        logger.error("DATABASE_URL no configurado.")
        raise ValueError("DATABASE_URL no configurado")
    results["database_url_set"] = True
    
    # Validar MQTT
    mqtt_host = os.getenv("MQTT_HOST", "").strip()
    if not mqtt_host:
        logger.error("MQTT_HOST no configurado.")
        raise ValueError("MQTT_HOST no configurado")
    results["mqtt_host_set"] = True
    
    # Log del resultado
    logger.info("Validación de seguridad: %s", results)
    return results


# ── Health Check ────────────────────────────────────────────────────────────

class HealthStatus:
    """Estado de salud del sistema."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.started_at = datetime.now(timezone.utc)
            cls._instance.last_check = datetime.now(timezone.utc)
        return cls._instance
    
    def get_status(self) -> dict:
        """Retorna estado de salud con uptime y timestamp."""
        now = datetime.now(timezone.utc)
        uptime = (now - self.started_at).total_seconds()
        return {
            "status": "ok",
            "timestamp": now.isoformat(),
            "uptime_seconds": uptime,
            "started_at": self.started_at.isoformat(),
        }
    
    def update_check(self):
        """Actualiza el timestamp del último check."""
        self.last_check = datetime.now(timezone.utc)


# ── Validación de IP (opcional para seguridad adicional) ────────────────────

_BLOCKED_IPS: set[str] = set()  # IPs bloqueadas temporalmente


def block_ip(ip: str, duration_minutes: int = 15) -> None:
    """Bloquea una IP temporalmente (en memoria, se pierde al reiniciar)."""
    _BLOCKED_IPS.add(ip)
    logger.warning("IP %s bloqueada por %d minutos", ip, duration_minutes)


def is_ip_blocked(ip: str) -> bool:
    """Verifica si una IP está bloqueada."""
    return ip in _BLOCKED_IPS


def unblock_ip(ip: str) -> None:
    """Desbloquea una IP."""
    _BLOCKED_IPS.discard(ip)
