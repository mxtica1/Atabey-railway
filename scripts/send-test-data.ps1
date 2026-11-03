# Script PowerShell para enviar datos de prueba al endpoint HTTP POST
# Uso: .\send-test-data.ps1
# Requiere: ngrok tunnel corriendo en otra terminal

$utcNow = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")

$payload = @{
    device_id = "VANTROI-TEST"
    buffer_id = "prueba-$(Get-Date -Format 'yyyyMMddHHmmss')"
    readings = @(
        @{
            sensor_id = "TEMP-01"
            value = 28.5
            unit = "C"
            timestamp = $utcNow
            sequence = 1
        },
        @{
            sensor_id = "HR-01"
            value = 72
            unit = "bpm"
            timestamp = $utcNow
            sequence = 2
        }
    )
} | ConvertTo-Json -Depth 5

Write-Host "📤 Enviando datos de prueba..."
Write-Host "Timestamp: $utcNow"
Write-Host ""

try {
    $response = Invoke-WebRequest -Uri "https://mayflower-motto-sublime.ngrok-free.dev/readings/batch" `
        -Method POST `
        -ContentType "application/json" `
        -Body $payload `
        -UseBasicParsing

    Write-Host "✅ HTTP Status: $($response.StatusCode)"
    Write-Host ""
    Write-Host "📊 Response:"
    $response.Content | ConvertFrom-Json | Format-List
}
catch {
    Write-Host "❌ Error en la solicitud:"
    Write-Host $_.Exception.Message
    if ($_.Exception.Response) {
        Write-Host "Status Code: $($_.Exception.Response.StatusCode.Value)"
        $streamReader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "Response Body: $($streamReader.ReadToEnd())"
    }
}
