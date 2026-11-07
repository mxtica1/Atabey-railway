#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Simula envío de datos de Vantroi al sistema Atabey
    
.DESCRIPTION
    Envía exactamente los 11 sensores que Vantroi va a enviar
    para verificar que aparecen en el dashboard
    
.EXAMPLE
    .\test-vantroi-simulation.ps1
#>

$BackendUrl = "https://atabey-backend-k7kh.onrender.com/readings/single"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "TEST VANTROI SIMULATION" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Obtener timestamp actual en ISO 8601 UTC
$timestamp = [System.DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")

# Array de sensores a enviar (11 mediciones)
$sensors = @(
    # Sensor Ambiental (3 mediciones)
    @{ device_id = "EVA-01"; sensor_id = "TEMP-01"; value = 28.5; unit = "C"; name = "Temperatura Ambiente" },
    @{ device_id = "EVA-01"; sensor_id = "HUM-01"; value = 62.3; unit = "%"; name = "Humedad Relativa" },
    @{ device_id = "EVA-01"; sensor_id = "EVA-PRESS-01"; value = 1013.25; unit = "hPa"; name = "Presion Atmosferica" },
    
    # Sensor Cardiaco (1 medicion)
    @{ device_id = "EVA-01"; sensor_id = "HR-01"; value = 78.0; unit = "bpm"; name = "Pulso Cardiaco" },
    
    # Sensor de Movimiento (4 mediciones)
    @{ device_id = "EVA-01"; sensor_id = "ACC-X-01"; value = 0.45; unit = "m/s²"; name = "Aceleracion X" },
    @{ device_id = "EVA-01"; sensor_id = "ACC-Y-01"; value = -0.23; unit = "m/s²"; name = "Aceleracion Y" },
    @{ device_id = "EVA-01"; sensor_id = "ACC-Z-01"; value = 9.81; unit = "m/s²"; name = "Aceleracion Z" },
    @{ device_id = "EVA-01"; sensor_id = "ACTIVITY-01"; value = 1; unit = "codigo"; name = "Actividad (Walking)" },
    
    # Sensor Temperatura Corporal (1 medicion)
    @{ device_id = "EVA-01"; sensor_id = "BTEMP-01"; value = 36.9; unit = "C"; name = "Temperatura Corporal" },
    
    # Sensor de Luz (1 medicion)
    @{ device_id = "ESP32-01"; sensor_id = "LUX-01"; value = 2450.0; unit = "lux"; name = "Intensidad Luminica (Domo)" },
    
    # Bonus: SpO2 (bonus si Vantroi lo tiene)
    @{ device_id = "EVA-01"; sensor_id = "SPO2-01"; value = 96.5; unit = "%"; name = "Saturacion de Oxigeno" }
)

Write-Host "Enviando $($sensors.Count) mediciones de prueba..." -ForegroundColor Yellow
Write-Host "Timestamp: $timestamp" -ForegroundColor Gray
Write-Host ""

$successCount = 0
$failCount = 0

foreach ($sensor in $sensors) {
    $payload = @{
        device_id = $sensor.device_id
        sensor_id = $sensor.sensor_id
        timestamp = $timestamp
        value = $sensor.value
        unit = $sensor.unit
        sequence = 1
    } | ConvertTo-Json
    
    try {
        $response = Invoke-WebRequest -Uri $BackendUrl `
            -Method Post `
            -ContentType "application/json" `
            -Body $payload `
            -UseBasicParsing `
            -ErrorAction Stop
        
        if ($response.StatusCode -eq 200) {
            $ack = $response.Content | ConvertFrom-Json
            Write-Host "[OK] $($sensor.sensor_id) — $($sensor.name)" -ForegroundColor Green
            Write-Host "      Valor: $($sensor.value) $($sensor.unit) | DB-ID: $($ack.items[0].db_id)" -ForegroundColor Gray
            $successCount++
        } else {
            Write-Host "[ERROR] $($sensor.sensor_id) — HTTP $($response.StatusCode)" -ForegroundColor Red
            $failCount++
        }
    } catch {
        Write-Host "[ERROR] $($sensor.sensor_id) — $($_.Exception.Message)" -ForegroundColor Red
        $failCount++
    }
    
    Start-Sleep -Milliseconds 500
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "RESULTADO:" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Exitosos: $successCount/$($sensors.Count)" -ForegroundColor Green
Write-Host "Fallidos: $failCount/$($sensors.Count)" -ForegroundColor $(if ($failCount -eq 0) { "Green" } else { "Red" })
Write-Host ""

if ($successCount -eq $sensors.Count) {
    Write-Host "✅ TODOS LOS DATOS ENVIADOS CORRECTAMENTE" -ForegroundColor Green
    Write-Host ""
    Write-Host "Verifica en el dashboard:" -ForegroundColor Cyan
    Write-Host "  → https://atabey-frontend.onrender.com" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Busca los valores que acabamos de enviar en:" -ForegroundColor Cyan
    Write-Host "  • Panel TRIPULANTE → Signos Vitales (Pulso: 78 bpm, Temp: 36.9°C)" -ForegroundColor Yellow
    Write-Host "  • Panel TRIPULANTE → Soporte de Vida (Temp: 28.5°C, Humedad: 62.3%, Presion: 1013.25 hPa)" -ForegroundColor Yellow
    Write-Host "  • Panel TRIPULANTE → Movimiento (Aceleraciones X, Y, Z)" -ForegroundColor Yellow
    Write-Host "  • Panel DOMO → Ambiente (Luz: 2450 lux)" -ForegroundColor Yellow
} else {
    Write-Host "❌ ALGUNOS DATOS FALLARON" -ForegroundColor Red
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
