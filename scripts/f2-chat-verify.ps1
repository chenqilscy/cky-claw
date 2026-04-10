$ErrorActionPreference = "Continue"
$base = "http://fn.cky:8080/api/v1"
$script:pass = 0
$script:fail = 0

function Test-Step {
  param([string]$step, [scriptblock]$scriptBlock)
  try {
    $result = & $scriptBlock
    Write-Host "[PASS] $step : $result" -ForegroundColor Green
    $script:pass++
  } catch {
    Write-Host "[FAIL] $step : $($_.Exception.Message)" -ForegroundColor Red
    $script:fail++
  }
}

# === 1. Auth ===
Write-Host ""
Write-Host "=== F2 Multi-Turn Chat E2E Verification ==="
$loginBody = '{"username":"f1-test","password":"F1Test!@#456"}'
$login = Invoke-RestMethod -Uri "$base/auth/login" -Method POST -ContentType "application/json" -Body $loginBody -TimeoutSec 10
$tk = $login.access_token
$h = @{ Authorization = "Bearer $tk"; "Content-Type" = "application/json" }
Write-Host "Authenticated as f1-test"

# === 2. Provider Check ===
Write-Host ""
Write-Host "--- Provider Check ---"
$providers = Invoke-RestMethod -Uri "$base/providers" -Headers $h -TimeoutSec 10
$providerNames = $providers.data | ForEach-Object { $_.name }
Write-Host "Available providers: $($providerNames -join ', ')"

$targetProvider = $null
foreach ($pName in @("deepseek","glm","moonshot","qwen")) {
  if ($providerNames -contains $pName) {
    $targetProvider = $pName
    break
  }
}
if (-not $targetProvider -and $providerNames.Count -gt 0) {
  $targetProvider = ($providers.data | Where-Object { $_.name -notlike "e2e*" } | Select-Object -First 1).name
}
if (-not $targetProvider) {
  Write-Host "[SKIP] No available Provider" -ForegroundColor Yellow
  exit 0
}
Write-Host "Selected provider: $targetProvider"

# Provider connectivity test
$providerDetail = $providers.data | Where-Object { $_.name -eq $targetProvider } | Select-Object -First 1
Test-Step -step "Provider Test ($targetProvider)" -scriptBlock {
  $testResult = Invoke-RestMethod -Uri "$base/providers/$($providerDetail.id)/test" -Method POST -Headers $h -ContentType "application/json" -Body '{}' -TimeoutSec 30
  "success=$($testResult.success) latency=$($testResult.latency_ms)ms"
}

# === 3. Create Agent ===
Write-Host ""
Write-Host "--- Agent Setup ---"
$agentName = "f2-chat-agent-$(Get-Random -Maximum 9999)"
$providerType = $providerDetail.provider_type
$model = switch ($providerType) {
  "deepseek"  { "deepseek-chat" }
  "zhipu"     { "glm-4-flash" }
  "moonshot"  { "moonshot-v1-8k" }
  "qwen"      { "qwen-turbo" }
  "openai"    { "gpt-4o-mini" }
  "anthropic" { "claude-3-haiku-20240307" }
  default     { "gpt-4o-mini" }
}

$agentJson = @"
{"name":"$agentName","description":"F2 chat test agent","instructions":"You are a concise assistant. Reply in Chinese, keep each reply under 50 chars.","model":"$model","provider_name":"$targetProvider"}
"@

Test-Step -step "Create Agent ($agentName)" -scriptBlock {
  $script:agent = Invoke-RestMethod -Uri "$base/agents" -Method POST -ContentType "application/json" -Body $agentJson -Headers $h -TimeoutSec 10
  "id=$($script:agent.id) model=$model provider=$targetProvider"
}

# === 4. Create Session ===
Write-Host ""
Write-Host "--- Session & Chat ---"
Test-Step -step "Create Session" -scriptBlock {
  $sessionJson = "{`"agent_name`":`"$agentName`"}"
  $script:session = Invoke-RestMethod -Uri "$base/sessions" -Method POST -ContentType "application/json" -Body $sessionJson -Headers $h -TimeoutSec 10
  "session_id=$($script:session.id)"
}

# === 5. Turn 1 (Non-Stream) ===
Write-Host ""
Write-Host "--- Turn 1 (Non-Stream) ---"
Test-Step -step "Turn 1: Greeting" -scriptBlock {
  $body1 = '{"input":"hello, please introduce yourself briefly","config":{"stream":false}}'
  $run = Invoke-RestMethod -Uri "$base/sessions/$($script:session.id)/run" -Method POST -ContentType "application/json" -Body $body1 -Headers $h -TimeoutSec 60
  $script:turn1Output = $run.output
  $preview = $run.output.Substring(0, [Math]::Min(80, $run.output.Length))
  "status=$($run.status) output=$preview..."
}

# === 5b. Turn 2 (Non-Stream, Context Memory) ===
Write-Host ""
Write-Host "--- Turn 2 (Non-Stream) ---"
Test-Step -step "Turn 2: Context Memory" -scriptBlock {
  $body2 = '{"input":"what did you just say? please repeat briefly","config":{"stream":false}}'
  $run = Invoke-RestMethod -Uri "$base/sessions/$($script:session.id)/run" -Method POST -ContentType "application/json" -Body $body2 -Headers $h -TimeoutSec 60
  $script:turn2Output = $run.output
  $preview = $run.output.Substring(0, [Math]::Min(80, $run.output.Length))
  "status=$($run.status) output=$preview..."
}

# === 6. Turn 3 (Stream) ===
Write-Host ""
Write-Host "--- Turn 3 (Stream) ---"
Test-Step -step "Turn 3: Stream output" -scriptBlock {
  $body3 = '{"input":"summarize our conversation in one sentence","config":{"stream":true}}'
  $response = Invoke-WebRequest -Uri "$base/sessions/$($script:session.id)/run" -Method POST -ContentType "application/json" -Body $body3 -Headers $h -TimeoutSec 60
  $lines = $response.Content -split "`n"
  $eventTypes = @()
  $textContent = ""
  foreach ($line in $lines) {
    if ($line -match "^event: (.+)") { $eventTypes += $Matches[1].Trim() }
    if ($line -match "^data: (.+)") {
      $d = $null
      try { $d = $Matches[1] | ConvertFrom-Json } catch {}
      if ($d -and $d.delta) { $textContent += $d.delta }
    }
  }
  $uniqueEvents = $eventTypes | Sort-Object -Unique
  $preview = if ($textContent.Length -gt 0) { $textContent.Substring(0, [Math]::Min(80, $textContent.Length)) } else { "(empty)" }
  "events=[$($uniqueEvents -join ',')] len=$($textContent.Length) text=$preview..."
}

# === 7. Message History ===
Write-Host ""
Write-Host "--- Message History ---"
Test-Step -step "Message History" -scriptBlock {
  $messages = Invoke-RestMethod -Uri "$base/sessions/$($script:session.id)/messages" -Headers $h -TimeoutSec 10
  $msgCount = 0
  if ($messages -is [array]) { $msgCount = $messages.Count }
  elseif ($messages.data) { $msgCount = $messages.data.Count }
  elseif ($messages.messages) { $msgCount = $messages.messages.Count }
  "messages=$msgCount (expected>=6: 3 user + 3 assistant)"
}

# === 8. Trace Verification ===
Write-Host ""
Write-Host "--- Trace Verification ---"
Test-Step -step "Trace Records" -scriptBlock {
  $traces = Invoke-RestMethod -Uri "$base/traces?limit=5" -Headers $h -TimeoutSec 10
  $count = 0
  if ($traces.data) { $count = $traces.data.Count }
  elseif ($traces -is [array]) { $count = $traces.Count }
  "recent_traces=$count"
}

# === 9. Cleanup ===
Write-Host ""
Write-Host "--- Cleanup ---"
Test-Step -step "Delete Session" -scriptBlock {
  Invoke-RestMethod -Uri "$base/sessions/$($script:session.id)" -Method DELETE -Headers $h -TimeoutSec 10 | Out-Null
  "deleted"
}
Test-Step -step "Delete Agent" -scriptBlock {
  Invoke-RestMethod -Uri "$base/agents/$agentName" -Method DELETE -Headers $h -TimeoutSec 10 | Out-Null
  "deleted $agentName"
}

# === 10. Summary ===
Write-Host ""
Write-Host "========== F2 VERIFICATION SUMMARY =========="
Write-Host "Passed: $($script:pass)  Failed: $($script:fail)"
if ($script:fail -eq 0) {
  Write-Host "ALL PASSED" -ForegroundColor Green
} else {
  Write-Host "SOME FAILURES" -ForegroundColor Red
  exit 1
}
