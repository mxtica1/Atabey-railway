#!/bin/bash

# Script: Prueba de ingesta de datos a Render
# Uso: bash test-ingest.sh
# 
# Este script envía un dato de prueba al backend de Render
# para verificar que el endpoint esté funcionando.

BACKEND_URL="https://atabey-backend-k7kh.onrender.com"
INGEST_ENDPOINT="${BACKEND_URL}/api/ingest"

echo "=========================================="
echo "Atabey Telemetry — Test de Ingesta"
echo "=========================================="
echo ""
echo "Backend: ${BACKEND_URL}"
echo "Endpoint: ${INGEST_ENDPOINT}"
echo ""

# Generar timestamp ISO 8601 actual
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Payload de prueba
PAYLOAD=$(cat <<EOF
{
  "device_id": "ESP32-TEST",
  "sensor_id": "TEMP-TEST",
  "timestamp": "${TIMESTAMP}",
  "value": 25.5,
  "unit": "C",
  "sequence": 1
}
EOF
)

echo "📤 Enviando dato de prueba..."
echo ""
echo "Payload:"
echo "$PAYLOAD"
echo ""

# Enviar POST
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  "$INGEST_ENDPOINT")

# Separar response body del status code
HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | head -n -1)

echo "📥 Respuesta:"
echo "HTTP ${HTTP_CODE}"
echo ""
echo "Body:"
echo "$BODY" | grep -o '{.*}' 2>/dev/null && echo "" || echo "$BODY"

echo ""
echo "=========================================="

# Interpretar resultado
if [ "$HTTP_CODE" = "200" ]; then
  echo "✅ Éxito! Endpoint funcionando."
  echo ""
  echo "Próximo paso: verificar datos en el dashboard"
  echo "→ https://atabey-frontend.onrender.com"
  exit 0
elif [ "$HTTP_CODE" = "000" ]; then
  echo "❌ Error de conexión (sin respuesta HTTP)"
  echo ""
  echo "Posibles causas:"
  echo "  1. Render backend está en cold start (primer request tarda ~30s)"
  echo "  2. No hay conexión a Internet"
  echo "  3. La URL no es accesible"
  echo ""
  echo "Intenta de nuevo en 30 segundos..."
  exit 1
else
  echo "❌ Error HTTP ${HTTP_CODE}"
  echo ""
  echo "Verifica:"
  echo "  1. URL correcta: ${INGEST_ENDPOINT}"
  echo "  2. JSON válido"
  echo "  3. Backend logs: ${BACKEND_URL}/docs"
  exit 1
fi
