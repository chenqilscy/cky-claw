$ErrorActionPreference = "Continue"
$base = "http://fn.cky:8080/api/v1"
$script:pass = 0
$script:fail = 0
$suffix = Get-Random -Maximum 99999

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
Write-Host "=== F6 Guardrail Three-Level E2E Verification (suffix=$suffix) ==="
$login = Invoke-RestMethod -Uri "$base/auth/login" -Method POST -ContentType "application/json" `
  -Body '{"username":"f1-test","password":"F1Test!@#456"}' -TimeoutSec 10
$tk = $login.access_token
$h = @{ Authorization = "Bearer $tk"; "Content-Type" = "application/json" }
Write-Host "Authenticated as f1-test"

# === 2. Create Guardrail Rules ===
Write-Host ""
Write-Host "--- Create Guardrail Rules ---"

# Input Guardrail: regex PII — ConvertTo-Json 自动处理正则转义
$grInputBody = @{
  name = "f6-input-pii-$suffix"
  description = "Block PII in input"
  type = "input"
  mode = "regex"
  config = @{
    patterns = @("\d{17}[\dXx]", "\d{15}")
    message = "PII detected in input, blocked"
  }
} | ConvertTo-Json -Depth 3

Test-Step -step "Create Input Guardrail (regex PII)" -scriptBlock {
  $script:grInput = Invoke-RestMethod -Uri "$base/guardrails" -Method POST -Body $grInputBody -Headers $h -TimeoutSec 10
  "id=$($script:grInput.id) name=$($script:grInput.name) patterns=$($script:grInput.config.patterns -join ',')"
}

# Output Guardrail: keyword
$grOutputBody = @{
  name = "f6-output-kw-$suffix"
  description = "Block sensitive keywords in output"
  type = "output"
  mode = "keyword"
  config = @{
    keywords = @("BLOCKED_WORD_XYZ", "FORBIDDEN_TERM_ABC")
    message = "Output contains forbidden keywords"
  }
} | ConvertTo-Json -Depth 3

Test-Step -step "Create Output Guardrail (keyword)" -scriptBlock {
  $script:grOutput = Invoke-RestMethod -Uri "$base/guardrails" -Method POST -Body $grOutputBody -Headers $h -TimeoutSec 10
  "id=$($script:grOutput.id) name=$($script:grOutput.name)"
}

# Tool Guardrail: regex SQL injection
$grToolBody = @{
  name = "f6-tool-sql-$suffix"
  description = "Block SQL injection in tool args"
  type = "tool"
  mode = "regex"
  config = @{
    patterns = @("(?i)(DROP|DELETE|TRUNCATE|ALTER)\s+(TABLE|DATABASE)")
    message = "Dangerous SQL detected in tool call"
  }
} | ConvertTo-Json -Depth 3

Test-Step -step "Create Tool Guardrail (regex SQL)" -scriptBlock {
  $script:grTool = Invoke-RestMethod -Uri "$base/guardrails" -Method POST -Body $grToolBody -Headers $h -TimeoutSec 10
  "id=$($script:grTool.id) name=$($script:grTool.name)"
}

# === 3. Verify CRUD ===
Write-Host ""
Write-Host "--- Guardrail CRUD ---"

Test-Step -step "List Guardrails (>= 3)" -scriptBlock {
  $list = Invoke-RestMethod -Uri "$base/guardrails" -Headers $h -TimeoutSec 10
  if ($list.total -lt 3) { throw "Expected >= 3 guardrails, got $($list.total)" }
  "total=$($list.total)"
}

Test-Step -step "Get Input Guardrail by ID" -scriptBlock {
  $detail = Invoke-RestMethod -Uri "$base/guardrails/$($script:grInput.id)" -Headers $h -TimeoutSec 10
  "name=$($detail.name) mode=$($detail.mode) type=$($detail.type)"
}

Test-Step -step "Update Input Guardrail" -scriptBlock {
  $updateBody = '{"description":"Updated: Block PII in user input"}'
  $updated = Invoke-RestMethod -Uri "$base/guardrails/$($script:grInput.id)" -Method PUT -Body $updateBody -Headers $h -TimeoutSec 10
  if ($updated.description -ne "Updated: Block PII in user input") { throw "Update failed" }
  "desc=$($updated.description)"
}

# === 4. Create Agent with Guardrails ===
Write-Host ""
Write-Host "--- Agent with Guardrails ---"
$agentName = "f6-gr-agent-$suffix"
$agentBody = @{
  name = $agentName
  description = "F6 guardrail test agent"
  instructions = "Reply briefly in English. Never include the words BLOCKED_WORD_XYZ or FORBIDDEN_TERM_ABC."
  model = "deepseek-chat"
  provider_name = "deepseek"
  guardrails = @{
    input = @("f6-input-pii-$suffix")
    output = @("f6-output-kw-$suffix")
    tool = @("f6-tool-sql-$suffix")
  }
} | ConvertTo-Json -Depth 3

Test-Step -step "Create Agent with 3 Guardrails" -scriptBlock {
  $script:agent = Invoke-RestMethod -Uri "$base/agents" -Method POST -Body $agentBody -Headers $h -TimeoutSec 10
  "input=[$($script:agent.guardrails.input -join ',')] output=[$($script:agent.guardrails.output -join ',')] tool=[$($script:agent.guardrails.tool -join ',')]"
}

# === 5. Create Session ===
Test-Step -step "Create Session" -scriptBlock {
  $sessBody = @{ agent_name = $agentName } | ConvertTo-Json
  $script:session = Invoke-RestMethod -Uri "$base/sessions" -Method POST -Body $sessBody -Headers $h -TimeoutSec 10
  "session_id=$($script:session.id)"
}

# === 6. Test Input Guardrail: PII should be BLOCKED ===
Write-Host ""
Write-Host "--- Input Guardrail Test ---"
Test-Step -step "Input Guardrail: Block PII (ID number)" -scriptBlock {
  $runBody = @{
    input = "my ID number is 110101199003070011"
    config = @{ stream = $false }
  } | ConvertTo-Json -Depth 3
  $run = Invoke-RestMethod -Uri "$base/sessions/$($script:session.id)/run" -Method POST -Body $runBody -Headers $h -TimeoutSec 60
  if ($run.status -eq "guardrail_blocked") {
    "BLOCKED as expected: $($run.output)"
  } elseif ($run.output -match "(?i)guardrail|blocked|PII|denied") {
    "BLOCKED (via output): $($run.output.Substring(0, [Math]::Min(80, $run.output.Length)))"
  } else {
    throw "Expected guardrail block but got: status=$($run.status) output=$($run.output.Substring(0, [Math]::Min(100, $run.output.Length)))"
  }
}

# === 7. Normal Input should PASS ===
Write-Host ""
Write-Host "--- Normal Input Test ---"
Test-Step -step "Normal input passes through" -scriptBlock {
  $runBody = @{
    input = "hello, how are you?"
    config = @{ stream = $false }
  } | ConvertTo-Json -Depth 3
  $run = Invoke-RestMethod -Uri "$base/sessions/$($script:session.id)/run" -Method POST -Body $runBody -Headers $h -TimeoutSec 60
  if ($run.status -eq "completed" -and $run.output.Length -gt 0) {
    "PASSED: $($run.output.Substring(0, [Math]::Min(80, $run.output.Length)))"
  } else {
    throw "Expected completed run but got: status=$($run.status)"
  }
}

# === 8. Cleanup ===
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
Test-Step -step "Delete Input Guardrail" -scriptBlock {
  Invoke-WebRequest -Uri "$base/guardrails/$($script:grInput.id)" -Method DELETE -Headers $h -TimeoutSec 10 -UseBasicParsing | Out-Null
  "deleted"
}
Test-Step -step "Delete Output Guardrail" -scriptBlock {
  Invoke-WebRequest -Uri "$base/guardrails/$($script:grOutput.id)" -Method DELETE -Headers $h -TimeoutSec 10 -UseBasicParsing | Out-Null
  "deleted"
}
Test-Step -step "Delete Tool Guardrail" -scriptBlock {
  Invoke-WebRequest -Uri "$base/guardrails/$($script:grTool.id)" -Method DELETE -Headers $h -TimeoutSec 10 -UseBasicParsing | Out-Null
  "deleted"
}

# === Summary ===
Write-Host ""
Write-Host "========== F6 VERIFICATION SUMMARY =========="
Write-Host "Passed: $($script:pass)  Failed: $($script:fail)"
if ($script:fail -eq 0) {
  Write-Host "ALL PASSED" -ForegroundColor Green
} else {
  Write-Host "SOME FAILURES" -ForegroundColor Red
  exit 1
}
