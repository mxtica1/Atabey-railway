from fastapi import WebSocket
from typing import Dict
import json
import logging
import asyncio

logger = logging.getLogger(__name__)

# Sensor IDs clasificados como biométricos — acceso solo para administrador/control_mision
BIOMETRIC_SENSORS = {"HR-01", "SPO2-01", "BTEMP-01"}


class ConnectionManager:
    def __init__(self):
        # {websocket: rol_del_usuario}
        self.connections: Dict[WebSocket, str] = {}
        self.loop = None

    def set_loop(self, loop):
        self.loop = loop

    async def connect(self, websocket: WebSocket, rol: str):
        """Acepta el WebSocket y registra el rol del usuario."""
        await websocket.accept()
        self.connections[websocket] = rol
        logger.info(
            "WebSocket connect [rol=%s]. Total clients: %d", rol, len(self.connections)
        )

    def disconnect(self, websocket: WebSocket):
        if websocket in self.connections:
            del self.connections[websocket]
            logger.info("WebSocket disconnect. Total clients: %d", len(self.connections))

    async def broadcast(self, message: dict):
        """
        Envía el mensaje a todas las conexiones activas, respetando la regla de acceso:
        - Observador NO recibe sensores biométricos (HR-01, SPO2-01, BTEMP-01).
        - Administrador y Control de misión reciben todo.
        """
        sensor_id = message.get("sensor_id", "")
        is_biometric = sensor_id in BIOMETRIC_SENSORS
        msg_str = json.dumps(message)

        dead = []
        for ws, rol in list(self.connections.items()):
            # Filtrar biométricos para observador
            if is_biometric and rol == "observador":
                continue
            try:
                await ws.send_text(msg_str)
            except Exception as exc:
                logger.error("Error broadcasting to WS: %s", exc)
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws)

    def broadcast_sync(self, message: dict):
        """Puente thread-safe desde el hilo MQTT hacia el event loop de FastAPI."""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self.loop)

    # Propiedad de compatibilidad para tests que acceden a active_connections
    @property
    def active_connections(self):
        return list(self.connections.keys())


manager = ConnectionManager()
