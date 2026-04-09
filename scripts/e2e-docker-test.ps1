#!/usr/bin/env pwsh
# CkyClaw Docker E2E API 验证脚本
param(
    [string]$Base = "http://localhost:8000",
    [string]$Username = "e2eadmin",
    [string]$Password = "Test123456!"
)

$ErrorActionPreference = "Continue"
$pass = 0; $fail = 0
$ts = Get-Date -Format "yyyyMMddHHmmss"
$agentName = "e2e-agent-$ts"

function Test-Api {
    param([string]$Name, [scriptblock]$Block)
    try {
        $result = & $Block
        Write-Host "  [PASS] $Name" -ForegroundColor Green
        $script:pass++
        return $result
    } catch {
        Write-Host "  [FAIL] $Name — $($_.Exception.Message)" -ForegroundColor Red
        $script:fail++
        return $null
    }
}

Write-Host "`n========== CkyClaw E2E API Test ==========" -ForegroundColor Cyan

# --- Auth ---
Write-Host "`n--- Auth ---" -ForegroundColor Yellow
Test-Api "Health Check" { Invoke-RestMethod "$Base/health" }
Test-Api "Health Deep" { Invoke-RestMethod "$Base/health/deep" }

$login = Test-Api "Login" {
    Invoke-RestMethod "$Base/api/v1/auth/login" -Method POST -ContentType "application/json" `
        -Body (@{username=$Username;password=$Password} | ConvertTo-Json)
}
$token = $login.access_token
$h = @{Authorization="Bearer $token"}

Test-Api "Get /me" { Invoke-RestMethod "$Base/api/v1/auth/me" -Headers $h }

# --- Agent CRUD ---
Write-Host "`n--- Agent CRUD ---" -ForegroundColor Yellow
Test-Api "Create Agent" {
    $body = @{name=$agentName;instructions="E2E test";model="gpt-4o-mini"} | ConvertTo-Json
    Invoke-RestMethod "$Base/api/v1/agents" -Method POST -Headers $h -ContentType "application/json" -Body $body
}
Test-Api "List Agents" { Invoke-RestMethod "$Base/api/v1/agents" -Headers $h }
Test-Api "Get Agent" { Invoke-RestMethod "$Base/api/v1/agents/$agentName" -Headers $h }
Test-Api "Update Agent" {
    Invoke-RestMethod "$Base/api/v1/agents/$agentName" -Method PUT -Headers $h -ContentType "application/json" `
        -Body '{"instructions":"Updated by E2E"}'
}

# --- Provider ---
Write-Host "`n--- Provider ---" -ForegroundColor Yellow
$providerName = "e2e-provider-$ts"
Test-Api "Create Provider" {
    $body = @{name=$providerName;provider_type="openai";base_url="https://api.openai.com/v1";api_key="sk-test-fake-key"} | ConvertTo-Json
    Invoke-RestMethod "$Base/api/v1/providers" -Method POST -Headers $h -ContentType "application/json" -Body $body
}
Test-Api "List Providers" { Invoke-RestMethod "$Base/api/v1/providers" -Headers $h }

# --- Tool Groups ---
Write-Host "`n--- Tool Groups ---" -ForegroundColor Yellow
$tg = Test-Api "List Tool Groups" { Invoke-RestMethod "$Base/api/v1/tool-groups" -Headers $h }
if ($tg) {
    $names = ($tg.data | ForEach-Object { $_.name }) -join ", "
    Write-Host "    Groups: $names" -ForegroundColor DarkGray
}

# --- Templates ---
Write-Host "`n--- Templates ---" -ForegroundColor Yellow
Test-Api "Seed Templates" {
    Invoke-RestMethod "$Base/api/v1/agent-templates/seed" -Method POST -Headers $h
}
$tmpl = Test-Api "List Templates" { Invoke-RestMethod "$Base/api/v1/agent-templates" -Headers $h }
if ($tmpl) { Write-Host "    Count: $($tmpl.total)" -ForegroundColor DarkGray }

# --- Session ---
Write-Host "`n--- Session ---" -ForegroundColor Yellow
$sess = Test-Api "Create Session" {
    $body = @{agent_name=$agentName} | ConvertTo-Json
    Invoke-RestMethod "$Base/api/v1/sessions" -Method POST -Headers $h -ContentType "application/json" -Body $body
}
if ($sess) {
    $sid = $sess.id
    Test-Api "Get Session" { Invoke-RestMethod "$Base/api/v1/sessions/$sid" -Headers $h }
    Test-Api "List Sessions" { Invoke-RestMethod "$Base/api/v1/sessions" -Headers $h }
}

# --- Traces ---
Write-Host "`n--- Traces ---" -ForegroundColor Yellow
Test-Api "List Traces" { Invoke-RestMethod "$Base/api/v1/traces" -Headers $h }

# --- Token Usage ---
Write-Host "`n--- Token Usage ---" -ForegroundColor Yellow
Test-Api "Token Usage Summary" { Invoke-RestMethod "$Base/api/v1/token-usage/summary" -Headers $h }

# --- Guardrails ---
Write-Host "`n--- Guardrails ---" -ForegroundColor Yellow
Test-Api "List Guardrails" { Invoke-RestMethod "$Base/api/v1/guardrails" -Headers $h }

# --- Approvals ---
Write-Host "`n--- Approvals ---" -ForegroundColor Yellow
Test-Api "List Approvals" { Invoke-RestMethod "$Base/api/v1/approvals" -Headers $h }

# --- Dashboard ---
Write-Host "`n--- Dashboard ---" -ForegroundColor Yellow
Test-Api "APM Dashboard" { Invoke-RestMethod "$Base/api/v1/apm/dashboard" -Headers $h }

# --- Cleanup ---
Write-Host "`n--- Cleanup ---" -ForegroundColor Yellow
Test-Api "Delete Agent" {
    Invoke-RestMethod "$Base/api/v1/agents/$agentName" -Method DELETE -Headers $h
}

# --- Frontend ---
Write-Host "`n--- Frontend ---" -ForegroundColor Yellow
Test-Api "Frontend index.html" {
    $uri = [System.Uri]$Base
    $frontendUrl = "http://$($uri.Host):3000"
    $resp = Invoke-WebRequest $frontendUrl -UseBasicParsing
    if ($resp.StatusCode -ne 200) { throw "Status $($resp.StatusCode)" }
    if ($resp.Content -notmatch "CkyClaw") { throw "Content mismatch" }
    $resp
}

# --- Summary ---
Write-Host "`n========== Results ==========" -ForegroundColor Cyan
Write-Host "  PASS: $pass  FAIL: $fail  TOTAL: $($pass+$fail)" -ForegroundColor $(if ($fail -eq 0) {"Green"} else {"Red"})
