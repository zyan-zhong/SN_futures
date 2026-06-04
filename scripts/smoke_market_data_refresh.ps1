param(
  [string]$BaseUrl = "http://127.0.0.1:8765",
  [switch]$StartBackend
)

$ErrorActionPreference = "Stop"

function Write-Info($Message) {
  Write-Host "[SNInsightTerminal] $Message"
}

function Invoke-TerminalJson {
  param(
    [string]$Method,
    [string]$Path,
    [object]$Body = $null,
    [int]$TimeoutSec = 180
  )
  $uri = "$BaseUrl$Path"
  if ($Body -ne $null) {
    $json = $Body | ConvertTo-Json -Depth 8
    return Invoke-RestMethod -Method $Method -Uri $uri -Body $json -ContentType "application/json" -TimeoutSec $TimeoutSec
  }
  return Invoke-RestMethod -Method $Method -Uri $uri -TimeoutSec $TimeoutSec
}

function Invoke-OptionalTerminalJson {
  param(
    [string]$Method,
    [string]$Path,
    [int]$TimeoutSec = 30
  )
  try {
    return Invoke-TerminalJson -Method $Method -Path $Path -TimeoutSec $TimeoutSec
  } catch {
    return [ordered]@{
      status = "timeout_or_failed"
      path = $Path
      message_zh = "Optional diagnostics timed out or failed; market smoke conclusion can still be produced."
      error_message_zh = $_.Exception.Message
    }
  }
}

$startedProcess = $null
if ($StartBackend) {
  Write-Info "Starting local backend..."
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
  Write-Info "Checking Terminal API..."
  $docs = Invoke-TerminalJson -Method GET -Path "/api/terminal/docs"
  if (-not $docs) {
    throw "Terminal API is unavailable. Start the backend first or pass -StartBackend."
  }

  Write-Info "Refreshing real market data chain..."
  $refresh = Invoke-TerminalJson -Method POST -Path "/api/terminal/refresh/market" -Body @{ force = $true }

  Write-Info "Reading price-history chart payload..."
  $priceHistory = Invoke-TerminalJson -Method GET -Path "/api/terminal/charts/price-history"

  Write-Info "Reading runtime diagnostics..."
  $runtimeDiagnostics = Invoke-OptionalTerminalJson -Method GET -Path "/api/terminal/runtime-diagnostics" -TimeoutSec 30

  Write-Info "Reading provider details..."
  $providerDetail = Invoke-OptionalTerminalJson -Method GET -Path "/api/terminal/providers/status-detail" -TimeoutSec 30

  $outputs = Join-Path $env:LOCALAPPDATA "SNInsightTerminal\logs"
  New-Item -ItemType Directory -Force -Path $outputs | Out-Null
  $outputPath = Join-Path $outputs "market_data_smoke.json"

  $steps = @()
  if ($refresh.steps) { $steps = $refresh.steps }
  $marketStep = $steps | Where-Object { $_.step_name -eq "market" } | Select-Object -First 1
  $marketProviderStatus = $providerDetail.market_provider_status
  $finalStatus = $marketStep.final_status
  if (-not $finalStatus -and $marketProviderStatus) { $finalStatus = $marketProviderStatus.final_status }
  $points = @()
  if ($priceHistory.points) { $points = $priceHistory.points }
  $rowCount = $points.Count
  if ($marketStep.history_rows) { $rowCount = [int]$marketStep.history_rows }

  $realtimeSuccess = $false
  $historySuccess = $false
  $attemptCount = 0
  if ($marketProviderStatus) {
    $realtimeAttempts = @($marketProviderStatus.realtime_attempts)
    $historyAttempts = @($marketProviderStatus.history_attempts)
    $shfeAttempts = @($marketProviderStatus.shfe_attempts)
    $attemptCount = $realtimeAttempts.Count + $historyAttempts.Count + $shfeAttempts.Count
    $realtimeSuccess = @($realtimeAttempts | Where-Object { $_.success -eq $true }).Count -gt 0
    $historySuccess = @($historyAttempts | Where-Object { $_.success -eq $true }).Count -gt 0
  }

  $fromCache = $false
  if ($marketStep -and $marketStep.from_cache -ne $null) {
    $fromCache = [bool]$marketStep.from_cache
  } elseif ($marketProviderStatus -and $marketProviderStatus.final_status -eq "cache_only") {
    $fromCache = $true
  }

  $summary = [ordered]@{
    generated_at = (Get-Date).ToString("s")
    base_url = $BaseUrl
    refresh_market = $refresh
    price_history = $priceHistory
    runtime_diagnostics = $runtimeDiagnostics
    provider_detail = $providerDetail
    conclusion = [ordered]@{
      realtime_success = $realtimeSuccess
      history_success = $historySuccess
      provider_attempt_count = $attemptCount
      history_row_count = $rowCount
      final_status = $finalStatus
      from_cache = $fromCache
      can_chart = ($rowCount -ge 20)
      enough_for_real_model_analysis = ($rowCount -ge 60 -and $finalStatus -ne "cache_only")
      prediction_policy = "No active model or insufficient real history means no prediction; no baseline or fake prediction is generated."
    }
  }

  $summary | ConvertTo-Json -Depth 18 | Set-Content -Path $outputPath -Encoding UTF8

  Write-Host ""
  Write-Info "Market data smoke conclusion:"
  Write-Host "  realtime_success: $realtimeSuccess"
  Write-Host "  history_success: $historySuccess"
  Write-Host "  provider_attempt_count: $attemptCount"
  Write-Host "  history_row_count: $rowCount"
  Write-Host "  final_status: $finalStatus"
  Write-Host "  from_cache: $fromCache"
  Write-Host "  can_chart: $($rowCount -ge 20)"
  Write-Host "  enough_for_real_model_analysis: $($rowCount -ge 60 -and $finalStatus -ne 'cache_only')"
  Write-Host "  prediction_policy: no active model or insufficient real history => no prediction."
  Write-Host "  output_file: $outputPath"
} finally {
  if ($startedProcess -ne $null -and -not $startedProcess.HasExited) {
    Write-Info "Stopping backend started by this smoke run..."
    Stop-Process -Id $startedProcess.Id -Force -ErrorAction SilentlyContinue
  }
}
