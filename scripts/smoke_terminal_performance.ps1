param(
  [string]$BaseUrl = "http://127.0.0.1:8765",
  [switch]$StartBackend,
  [int]$WarmupCount = 1
)

$ErrorActionPreference = "Stop"

function Write-Info {
  param([string]$Message)
  Write-Host "[SNInsightTerminal] $Message"
}

function Invoke-TimedRequest {
  param(
    [string]$Name,
    [string]$Path,
    [int]$BudgetMs,
    [string]$Method = "GET",
    [int]$TimeoutSec = 10
  )

  $uri = "$BaseUrl$Path"
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  $statusCode = 0
  $ok = $false
  $errorMessage = ""
  try {
    if ($Path -eq "/terminal") {
      $response = Invoke-WebRequest -UseBasicParsing -Method $Method -Uri $uri -TimeoutSec $TimeoutSec
      $statusCode = [int]$response.StatusCode
      $ok = $statusCode -ge 200 -and $statusCode -lt 300
    } else {
      $response = Invoke-WebRequest -UseBasicParsing -Method $Method -Uri $uri -TimeoutSec $TimeoutSec
      $statusCode = [int]$response.StatusCode
      $ok = $statusCode -ge 200 -and $statusCode -lt 300
    }
  } catch {
    $errorMessage = $_.Exception.Message
  } finally {
    $sw.Stop()
  }

  $duration = [math]::Round($sw.Elapsed.TotalMilliseconds, 3)
  return [ordered]@{
    name = $Name
    path = $Path
    status_code = $statusCode
    duration_ms = $duration
    budget_ms = $BudgetMs
    within_budget = ($ok -and $duration -le $BudgetMs)
    ok = $ok
    error_message_zh = $errorMessage
  }
}

$startedProcess = $null
if ($StartBackend) {
  Write-Info "Starting local backend for performance smoke..."
  $repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
  $srcPath = Join-Path $repoRoot "src"
  if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$srcPath;$env:PYTHONPATH"
  } else {
    $env:PYTHONPATH = $srcPath
  }
  $python = (Get-Command python -ErrorAction Stop).Source
  $port = ([System.Uri]$BaseUrl).Port
  $startedProcess = Start-Process -FilePath $python -ArgumentList "app_launcher.py", "--api-server", "--api-port", "$port" -WorkingDirectory $repoRoot -PassThru -WindowStyle Hidden
  Start-Sleep -Seconds 5
}

try {
  for ($i = 0; $i -lt $WarmupCount; $i++) {
    Invoke-TimedRequest -Name "warmup-summary" -Path "/api/terminal/summary" -BudgetMs 999999 -TimeoutSec 10 | Out-Null
    Invoke-TimedRequest -Name "warmup-system-health" -Path "/api/terminal/system-health" -BudgetMs 999999 -TimeoutSec 10 | Out-Null
    Invoke-TimedRequest -Name "warmup-snapshot-lite" -Path "/api/terminal/snapshot-lite" -BudgetMs 999999 -TimeoutSec 10 | Out-Null
  }

  $checks = @()
  $checks += Invoke-TimedRequest -Name "summary" -Path "/api/terminal/summary" -BudgetMs 300 -TimeoutSec 5
  $checks += Invoke-TimedRequest -Name "system-health" -Path "/api/terminal/system-health" -BudgetMs 300 -TimeoutSec 5
  $checks += Invoke-TimedRequest -Name "snapshot-lite" -Path "/api/terminal/snapshot-lite" -BudgetMs 500 -TimeoutSec 5
  $checks += Invoke-TimedRequest -Name "terminal-first-content" -Path "/terminal" -BudgetMs 2000 -TimeoutSec 10

  $passed = @($checks | Where-Object { -not $_.within_budget }).Count -eq 0
  $outputs = Join-Path $env:LOCALAPPDATA "SNInsightTerminal\logs"
  New-Item -ItemType Directory -Force -Path $outputs | Out-Null
  $outputPath = Join-Path $outputs "terminal_performance_smoke.json"

  $summary = [ordered]@{
    generated_at = (Get-Date).ToString("s")
    base_url = $BaseUrl
    passed = $passed
    no_global_loading_blocker_check = "Terminal shell and snapshot-lite are checked separately; browser smoke validates page-level blockers."
    checks = $checks
    policy = "This smoke does not train models, publish active models, or generate customer predictions."
  }
  $summary | ConvertTo-Json -Depth 8 | Set-Content -Path $outputPath -Encoding UTF8

  Write-Host ""
  Write-Info "Terminal performance smoke conclusion:"
  foreach ($check in $checks) {
    $status = if ($check.within_budget) { "PASS" } else { "WARN" }
    Write-Host ("  {0}: {1} ms / budget {2} ms => {3}" -f $check.name, $check.duration_ms, $check.budget_ms, $status)
    if ($check.error_message_zh) {
      Write-Host "    reason: $($check.error_message_zh)"
    }
  }
  Write-Host "  no_global_loading_blocker: checked by snapshot-lite separation and browser smoke"
  Write-Host "  output_file: $outputPath"

  if (-not $passed) {
    exit 1
  }
} finally {
  if ($startedProcess -ne $null -and -not $startedProcess.HasExited) {
    Write-Info "Stopping backend started by this smoke run..."
    Stop-Process -Id $startedProcess.Id -Force -ErrorAction SilentlyContinue
  }
}
