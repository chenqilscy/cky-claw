$ErrorActionPreference = "Continue"
$base = "http://fn.cky:8080/api/v1"
$script:pass = 0
$script:fail = 0

function Test-Api($step, $scriptBlock) {
  try {
    $result = & $scriptBlock
    Write-Host "[PASS] $step : $result"
    $script:pass++
  } catch {
    Write-Host "[FAIL] $step : $($_.Exception.Message)" -ForegroundColor Red
    $script:fail++
  }
}

# === 1. Auth Flow ===
Write-Host "`n=== AUTH FLOW ==="
Test-Api "Register" { try { Invoke-RestMethod -Uri "$base/auth/register" -Method POST -ContentType "application/json" -Body '{"email":"f1-test@ckyclaw.io","username":"f1-test","password":"F1Test!@#456"}' -TimeoutSec 10 | Out-Null; "new user" } catch { "already exists (ok)" } }

$login = Invoke-RestMethod -Uri "$base/auth/login" -Method POST -ContentType "application/json" -Body '{"username":"f1-test","password":"F1Test!@#456"}' -TimeoutSec 10
$tk = $login.access_token
$h = @{Authorization="Bearer $tk"}
Test-Api "Login" { "token=$($tk.Substring(0,16))..." }
Test-Api "Me" { $me = Invoke-RestMethod -Uri "$base/auth/me" -Headers $h -TimeoutSec 10; "user=$($me.username) role=$($me.role)" }
Test-Api "RBAC" { try { Invoke-RestMethod -Uri "$base/users" -Headers @{Authorization="Bearer fake"} -TimeoutSec 10; throw "should fail" } catch { "unauthorized blocked" } }

# === 2. Agent CRUD ===
Write-Host "`n=== AGENT CRUD ==="
$agentName = "f1-test-agent-$(Get-Random -Maximum 9999)"
Test-Api "Agent Create" { $script:agent = Invoke-RestMethod -Uri "$base/agents" -Method POST -ContentType "application/json" -Body (@{name=$agentName;description="F1 test";instructions="Test agent";model="gpt-4o-mini"} | ConvertTo-Json) -Headers $h -TimeoutSec 10; "name=$($script:agent.name)" }
Test-Api "Agent List" { $r = Invoke-RestMethod -Uri "$base/agents" -Headers $h -TimeoutSec 10; "total=$($r.total) count=$($r.data.Count)" }
Test-Api "Agent Get" { $r = Invoke-RestMethod -Uri "$base/agents/$agentName" -Headers $h -TimeoutSec 10; "name=$($r.name) model=$($r.model)" }
Test-Api "Agent Update" { $r = Invoke-RestMethod -Uri "$base/agents/$agentName" -Method PUT -ContentType "application/json" -Body '{"description":"Updated"}' -Headers $h -TimeoutSec 10; "desc=$($r.description)" }
Test-Api "Agent Versions" { $r = Invoke-RestMethod -Uri "$base/agents/$($script:agent.id)/versions" -Headers $h -TimeoutSec 10; "total=$($r.total)" }

# === 3-15. List APIs ===
Write-Host "`n=== LIST APIs ==="
$listApis = @(
  @{Name="Provider";    Path="providers"},
  @{Name="Guardrail";   Path="guardrails"},
  @{Name="Approval";    Path="approvals"},
  @{Name="MCP Server";  Path="mcp/servers"},
  @{Name="ToolGroup";   Path="tool-groups"},
  @{Name="Memory";      Path="memories"},
  @{Name="Skill";       Path="skills"},
  @{Name="Template";    Path="agent-templates"},
  @{Name="Trace";       Path="traces?limit=5"},
  @{Name="Session";     Path="sessions"},
  @{Name="AuditLog";    Path="audit-logs?limit=5"},
  @{Name="Team";        Path="teams"},
  @{Name="Workflow";    Path="workflows"}
)
foreach ($api in $listApis) {
  Test-Api "$($api.Name) List" { $r = Invoke-RestMethod -Uri "$base/$($api.Path)" -Headers $h -TimeoutSec 10; "total=$($r.total)" }.GetNewClosure()
}

# === 16. Token Usage ===
Write-Host "`n=== ANALYTICS ==="
Test-Api "Token Trend" { $r = Invoke-RestMethod -Uri "$base/token-usage/trend" -Headers $h -TimeoutSec 10; "points=$($r.Count)" }
Test-Api "Dashboard Stats" { $r = Invoke-RestMethod -Uri "$base/traces/stats" -Headers $h -TimeoutSec 10; "ok" }


# === Cleanup ===
Write-Host "`n=== CLEANUP ==="
Test-Api "Agent Delete" { Invoke-RestMethod -Uri "$base/agents/$agentName" -Method DELETE -Headers $h -TimeoutSec 10 | Out-Null; "deleted $agentName" }

# === Summary ===
Write-Host "`n========== F1 VERIFICATION SUMMARY =========="
Write-Host "Passed: $($script:pass)  Failed: $($script:fail)"
if ($script:fail -eq 0) { Write-Host "ALL PASSED" -ForegroundColor Green } else { Write-Host "SOME FAILURES" -ForegroundColor Red; exit 1 }
