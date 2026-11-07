#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Limpia la base de datos de Render (elimina datos de prueba)

.DESCRIPTION
    Obtiene token de admin y ejecuta DELETE /admin/data/readings

.PARAMETER Username
    Usuario admin (default: admin)

.PARAMETER Password
    Contraseña admin (default: admin_pass)

.PARAMETER BackendUrl
    URL del backend (default: https://atabey-backend-k7kh.onrender.com)
#>

param(
    [string]$Username = "admin",
    [string]$Password = "admin_pass",
    [string]$BackendUrl = "https://atabey-backend-k7kh.onrender.com"
)

Write-Host "Limpieza de Base de Datos (Render)" -ForegroundColor Cyan
Write-Host ""

# Step 1: Login
Write-Host "Paso 1: Obteniendo token de autenticacion..." -ForegroundColor Yellow
try {
    $loginResp = Invoke-WebRequest -Uri "$BackendUrl/auth/login" `
        -Method Post `
        -ContentType "application/x-www-form-urlencoded" `
        -Body "username=$Username&password=$Password" `
        -UseBasicParsing
    
    $token = ($loginResp.Content | ConvertFrom-Json).access_token
    Write-Host "[OK] Token obtenido" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Error al obtener token: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 2: Execute DELETE
Write-Host ""
Write-Host "Paso 2: Eliminando datos de prueba..." -ForegroundColor Yellow
try {
    $deleteResp = Invoke-WebRequest -Uri "$BackendUrl/admin/data/readings" `
        -Method Delete `
        -Headers @{ "Authorization" = "Bearer $token" } `
        -UseBasicParsing
    
    $result = $deleteResp.Content | ConvertFrom-Json
    
    Write-Host "[OK] Limpieza exitosa!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Resultado:" -ForegroundColor Cyan
    Write-Host "  Lecturas ANTES: $($result.readings_before)" -ForegroundColor Yellow
    Write-Host "  Lecturas DESPUES: $($result.readings_after)" -ForegroundColor Green
    Write-Host ""
    Write-Host "[LISTO] Base de datos limpia y lista para Vantroi" -ForegroundColor Green
    
} catch {
    Write-Host "[ERROR] Error al limpiar: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
