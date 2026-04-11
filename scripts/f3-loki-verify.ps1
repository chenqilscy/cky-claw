param(
    [string]$BaseUrl = "http://fn.cky:8080",
    [string]$LokiUrl = "http://fn.cky:3100",
    [string]$Username = "f6-eval",
    [string]$Password = "F6Eval!@#456"
)

$ErrorActionPreference = "Stop"

Write-Host "[F3] Step 1/4: login..."
$loginBody = @{ username = $Username; password = $Password } | ConvertTo-Json
$login = Invoke-RestMethod -Uri "$BaseUrl/api/v1/auth/login" -Method POST -ContentType "application/json" -Body $loginBody
$token = $login.access_token

Write-Host "[F3] Step 2/4: call health endpoint to generate logs..."
Invoke-RestMethod -Uri "$BaseUrl/health" -Method GET | Out-Null

Write-Host "[F3] Step 3/4: query Loki labels..."
$labels = Invoke-RestMethod -Uri "$LokiUrl/loki/api/v1/labels" -Method GET
$hasJob = $labels.data -contains "job"

Write-Host "[F3] Step 4/4: run LogQL queries..."
$queries = @(
    @{ Name = "Recent backend logs"; Query = "{job=\"backend\"}" },
    @{ Name = "Error count 5m"; Query = "sum(count_over_time({job=\"backend\", level=\"ERROR\"}[5m]))" },
    @{ Name = "Traceback count 10m"; Query = "sum(count_over_time({job=\"backend\"} |= \"Traceback\" [10m]))" }
)

foreach ($q in $queries) {
    $encoded = [System.Web.HttpUtility]::UrlEncode($q.Query)
    $uri = "$LokiUrl/loki/api/v1/query?query=$encoded"
    $resp = Invoke-RestMethod -Uri $uri -Method GET
    Write-Host (" - {0}: status={1}" -f $q.Name, $resp.status)
}

Write-Host "[F3] DONE"
Write-Host ("Labels contains 'job': {0}" -f $hasJob)
Write-Host "Sample LogQL queries:"
Write-Host "  1) {job=\"backend\"}"
Write-Host "  2) sum by (level) (count_over_time({job=\"backend\"}[5m]))"
Write-Host "  3) {job=\"backend\"} |= \"Traceback\""
