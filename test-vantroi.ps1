#!/usr/bin/env pwsh

$BackendUrl = "https://atabey-backend-k7kh.onrender.com/readings/single"

Write-Host "TEST VANTROI SIMULATION" -ForegroundColor Cyan
Write-Host "Enviando 11 mediciones de prueba..." -ForegroundColor Yellow
Write-Host ""

$timestamp = [System.DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")

$sensors = @(
    @{ device_id = "EVA-01"; sensor_id = "TEMP-01"; value = 28.5; unit = "C"; name = "Temp Ambiente" },
    @{ device_id = "EVA-01"; sensor_id = "HUM-01"; value = 62.3; unit = "%"; name = "Humedad" },
    @{ device_id = "EVA-01"; sensor_id = "EVA-PRESS-01"; value = 1013.25; unit = "hPa"; name = "Presion" },
    @{ device_id = "EVA-01"; sensor_id = "HR-01"; value = 78.0; unit = "bpm"; name = "Pulso" },
    @{ device_id = "EVA-01"; sensor_id = "ACC-X-01"; value = 0.45; unit = "m/s2"; name = "Accel X" },
    @{ device_id = "EVA-01"; sensor_id = "ACC-Y-01"; value = -0.23; unit = "m/s2"; name = "Accel Y" },
    @{ device_id = "EVA-01"; sensor_id = "ACC-Z-01"; value = 9.81; unit = "m/s2"; name = "Accel Z" },
    @{ device_id = "EVA-01"; sensor_id = "ACTIVITY-01"; value = 1; unit = "codigo"; name = "Actividad" },
    @{ device_id = "EVA-01"; sensor_id = "BTEMP-01"; value = 36.9; unit = "C"; name = "Temp Corporal" },
    @{ device_id = "ESP32-01"; sensor_id = "LUX-01"; value = 2450.0; unit = "lux"; name = "Luz Domo" },
    @{ device_id = "EVA-01"; sensor_id = "SPO2-01"; value = 96.5; unit = "%"; name = "SpO2" }
)

$success = 0
$fail = 0

foreach ($s in $sensors) {
    $json = @{
        device_id = $s.device_id
        sensor_id = $s.sensor_id
        timestamp = $timestamp
        value = $s.value
        unit = $s.unit
        sequence = 1
    } | ConvertTo-Json
    
    try {
        $resp = Invoke-WebRequest -Uri $BackendUrl -Method Post -ContentType "application/json" -Body $json -UseBasicParsing -ErrorAction Stop
        
        if ($resp.StatusCode -eq 200) {
            $ack = $resp.Content | ConvertFrom-Json
            Write-Host "[OK] $($s.sensor_id) - $($s.name): $($s.value) $($s.unit)" -ForegroundColor Green
            $success++
        }
    } catch {
        Write-Host "[FAIL] $($s.sensor_id) - Error" -ForegroundColor Red
        $fail++
    }
    
    Start-Sleep -Milliseconds 300
}

Write-Host ""
Write-Host "RESULTADO: $success exitosos, $fail fallidos" -ForegroundColor Cyan
Write-Host ""

if ($success -eq $sensors.Count) {
    Write-Host "PERFECTO: Todos los datos se enviaron." -ForegroundColor Green
    Write-Host ""
    Write-Host "Verifica en: https://atabey-frontend.onrender.com" -ForegroundColor Yellow
    Write-Host "Busca:" -ForegroundColor Cyan
    Write-Host "  - Panel TRIPULANTE: Pulso 78 bpm, Temp 36.9C, Presion 1013 hPa" -ForegroundColor Gray
    Write-Host "  - Panel DOMO: Luz 2450 lux" -ForegroundColor Gray
}
