param(
  [string]$SetupPath = "",
  [string]$InstalledRoot = "",
  [string]$DataDir = "",
  [switch]$UseTempDataDir,
  [int]$ApiPort = 0,
  [int]$TimeoutSeconds = 60,
  [switch]$SkipInstall,
  [switch]$KeepInstalled,
  [switch]$RunBrowserSmoke,
  [switch]$InjectLegacyPrivateSeed,
  [switch]$ExpectPrivateBundleKeys
)

$ErrorActionPreference = "Stop"

if ($ExpectPrivateBundleKeys) {
  throw "ExpectPrivateBundleKeys is disabled: installer smoke must validate local per-user provider configuration only."
}

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $SetupPath) {
  $SetupPath = Join-Path $ProjectRoot "release\SNInsightTerminal_Setup.exe"
}
$SmokeLogDir = Join-Path $env:TEMP "SNInsightTerminalSmoke"
$ReportPath = Join-Path $SmokeLogDir "installed_smoke_report.txt"
$InstalledRootWasSpecified = [bool]$InstalledRoot
if (-not $InstalledRoot) {
  $InstalledRoot = Join-Path $env:LOCALAPPDATA "Programs\SNInsightTerminal"
}
$InstallDir = $InstalledRoot
$ExePath = Join-Path $InstallDir "SNInsightTerminal.exe"
$StartMenuShortcut = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\SNInsightTerminal\SNInsightTerminal.lnk"
$CreatedTempDataDir = $false
if ($UseTempDataDir) {
  $DataDir = Join-Path $env:TEMP ("SNInsightTerminalSmokeData_" + [guid]::NewGuid().ToString("N"))
  $CreatedTempDataDir = $true
}
if ($DataDir) {
  $UserData = $DataDir
} else {
  $UserData = Join-Path $env:LOCALAPPDATA "SNInsightTerminal"
}
$TempDataDirPath = $UserData

function Write-SmokeLog {
  param([string]$Message)
  $line = "$(Get-Date -Format s) $Message"
  Write-Host $line
  Add-Content -Encoding UTF8 $ReportPath $line
}

function Assert-True {
  param([bool]$Condition, [string]$Message)
  if (-not $Condition) {
    throw $Message
  }
  Write-SmokeLog "PASS: $Message"
}

function Assert-False {
  param([bool]$Condition, [string]$Message)
  Assert-True (-not $Condition) $Message
}

function Assert-TextNotContains {
  param([string]$Text, [string[]]$Forbidden, [string]$Scope)
  foreach ($item in $Forbidden) {
    if ($Text -like "*$item*") {
      throw "$Scope contains forbidden content: $item"
    }
  }
  Write-SmokeLog "PASS: $Scope has no forbidden sensitive content."
}

function Assert-LegacySeedInjectionIsSafe {
  if (-not $InjectLegacyPrivateSeed) {
    return
  }
  if ($SkipInstall) {
    throw "InjectLegacyPrivateSeed requires installer execution and cannot be combined with SkipInstall."
  }
  if (-not $InstalledRootWasSpecified) {
    throw "InjectLegacyPrivateSeed requires an explicit temporary InstalledRoot."
  }

  $fullInstallRoot = [System.IO.Path]::GetFullPath($InstallDir)
  $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
  $defaultInstallRoot = [System.IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA "Programs\SNInsightTerminal"))
  if ($fullInstallRoot.Equals($defaultInstallRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "InjectLegacyPrivateSeed cannot target the default Programs\SNInsightTerminal install root."
  }
  if (-not $fullInstallRoot.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "InjectLegacyPrivateSeed requires an explicit temporary InstalledRoot under the system temp directory."
  }
  $leaf = Split-Path -Leaf $fullInstallRoot
  if (-not ($leaf -like "SNInsightTerminalInstall_*")) {
    throw "InjectLegacyPrivateSeed requires an explicit temporary InstalledRoot named SNInsightTerminalInstall_*."
  }
}

function Seed-LegacyPrivateBundle {
  if (-not $InjectLegacyPrivateSeed) {
    return
  }
  Assert-LegacySeedInjectionIsSafe
  $legacyPrivateDir = Join-Path $InstallDir "_internal\private"
  New-Item -ItemType Directory -Force -Path $legacyPrivateDir | Out-Null
  $legacySecrets = @{
    schema_version = 1
    secrets = @{
      SN_ALPHA_VANTAGE_KEY = "LEGACY_ALPHA_PRIVATE_SEED_SHOULD_BE_REMOVED"
      SN_NEWSAPI_KEY = "LEGACY_NEWS_PRIVATE_SEED_SHOULD_BE_REMOVED"
      SN_TUSHARE_TOKEN = "LEGACY_TUSHARE_PRIVATE_SEED_SHOULD_BE_REMOVED"
    }
  } | ConvertTo-Json -Depth 6
  Set-Content -Encoding UTF8 -Path (Join-Path $legacyPrivateDir "private_bundle_seed.json") -Value $legacySecrets
  Set-Content -Encoding UTF8 -Path (Join-Path $legacyPrivateDir "private_release_keys.json") -Value $legacySecrets
  Set-Content -Encoding UTF8 -Path (Join-Path $legacyPrivateDir "secrets.json") -Value $legacySecrets
  Set-Content -Encoding UTF8 -Path (Join-Path $legacyPrivateDir ".env") -Value "SN_ALPHA_VANTAGE_KEY=LEGACY_ALPHA_PRIVATE_SEED_SHOULD_BE_REMOVED"
  Write-SmokeLog "Seeded legacy private bundle files under temporary install root."
}

function Assert-LegacyPrivateBundleRemoved {
  if (-not $InjectLegacyPrivateSeed) {
    return
  }
  $legacyPrivateDir = Join-Path $InstallDir "_internal\private"
  $legacyFiles = @(
    (Join-Path $legacyPrivateDir "private_bundle_seed.json"),
    (Join-Path $legacyPrivateDir "private_release_keys.json"),
    (Join-Path $legacyPrivateDir "secrets.json"),
    (Join-Path $legacyPrivateDir ".env")
  )
  foreach ($legacyFile in $legacyFiles) {
    Assert-True (-not (Test-Path $legacyFile)) "legacy private bundle seed is removed from install root"
  }
  if (Test-Path $legacyPrivateDir) {
    $remaining = @(Get-ChildItem -LiteralPath $legacyPrivateDir -Force -ErrorAction SilentlyContinue)
    Assert-True ($remaining.Count -eq 0) "legacy private directory is empty or absent after install"
  } else {
    Assert-True $true "legacy private directory is empty or absent after install"
  }
}

function Stop-InstalledProcesses {
  Get-Process -Name "SNInsightTerminal" -ErrorAction SilentlyContinue | ForEach-Object {
    try {
      Stop-Process -Id $_.Id -Force -ErrorAction Stop
      Write-SmokeLog "Stopped existing SNInsightTerminal process: $($_.Id)"
    } catch {
      Write-SmokeLog "Failed to stop existing process: $($_.Exception.Message)"
    }
  }
}

function Invoke-SmokeRequest {
  param(
    [string]$Uri,
    [string]$Method = "GET",
    [object]$Body = $null,
    [int]$TimeoutSec = 10
  )
  $params = @{
    Uri = $Uri
    Method = $Method
    TimeoutSec = $TimeoutSec
  }
  if ($null -ne $Body) {
    $params["Body"] = ($Body | ConvertTo-Json -Depth 8)
    $params["ContentType"] = "application/json"
  }
  return Invoke-RestMethod @params
}

function Invoke-SmokeWebRequest {
  param([string]$Uri, [int]$TimeoutSec = 10)
  return Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec $TimeoutSec
}

function Wait-TerminalPort {
  param([int[]]$Ports, [int]$TimeoutSeconds = 60)
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    foreach ($candidatePort in $Ports) {
      try {
        $docs = Invoke-SmokeRequest -Uri "http://127.0.0.1:$candidatePort/api/terminal/docs" -TimeoutSec 5
        if ($null -ne $docs) {
          Write-SmokeLog "PASS: /api/terminal/docs responded on port $candidatePort"
          return $candidatePort
        }
      } catch {
        Start-Sleep -Milliseconds 250
      }
    }
  }
  throw "Timed out waiting for Terminal API on configured smoke ports."
}

function Assert-PortReleased {
  param([int]$Port, [int]$TimeoutSeconds = 20)
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $client = New-Object System.Net.Sockets.TcpClient
      $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
      $connected = $async.AsyncWaitHandle.WaitOne(300, $false)
      if ($connected) {
        $client.EndConnect($async)
        $client.Close()
        Start-Sleep -Milliseconds 300
        continue
      }
      $client.Close()
      Write-SmokeLog "PASS: port released: $Port"
      return
    } catch {
      Write-SmokeLog "PASS: port released: $Port"
      return
    }
  }
  throw "Port was not released after shutdown: $Port"
}

function Assert-NoSNInsightOrphanProcess {
  $remaining = @(Get-Process -Name "SNInsightTerminal" -ErrorAction SilentlyContinue)
  if ($remaining.Count -gt 0) {
    $ids = ($remaining | Select-Object -ExpandProperty Id) -join ","
    throw "SNInsightTerminal orphan process remains: $ids"
  }
  Write-SmokeLog "PASS: no SNInsightTerminal orphan process remains"
}

function Stop-SmokeProcessIfRunning {
  param(
    [object]$Process,
    [int]$TimeoutSeconds = 20
  )
  if (-not $Process) {
    return
  }
  $exitDeadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while (-not $Process.HasExited -and (Get-Date) -lt $exitDeadline) {
    Start-Sleep -Milliseconds 300
    $Process.Refresh()
  }
  if ($Process.HasExited) {
    Write-SmokeLog "PASS: installed process exited after shutdown API"
    return
  }
  Write-SmokeLog "WARN: installed process still running after shutdown API; forcing cleanup."
  Stop-Process -Id $Process.Id -Force
  try {
    Wait-Process -Id $Process.Id -Timeout 10 -ErrorAction Stop
  } catch {
    Write-SmokeLog "WARN: forced process cleanup did not report exit before timeout. $($_.Exception.Message)"
  }
}

function Set-SmokeEnvironmentValue {
  param([string]$Name, [string]$Value)
  if (-not $script:PreviousEnvironment.ContainsKey($Name)) {
    $script:PreviousEnvironment[$Name] = [Environment]::GetEnvironmentVariable($Name, "Process")
  }
  [Environment]::SetEnvironmentVariable($Name, $Value, "Process")
}

function Clear-SmokeEnvironmentValue {
  param([string]$Name)
  if (-not $script:PreviousEnvironment.ContainsKey($Name)) {
    $script:PreviousEnvironment[$Name] = [Environment]::GetEnvironmentVariable($Name, "Process")
  }
  [Environment]::SetEnvironmentVariable($Name, $null, "Process")
}

function Restore-SmokeEnvironment {
  foreach ($entry in $script:PreviousEnvironment.GetEnumerator()) {
    [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, "Process")
  }
}

function Configure-IsolatedSmokeEnvironment {
  New-Item -ItemType Directory -Force -Path $UserData | Out-Null
  foreach ($name in @(
    "SN_ALPHA_VANTAGE_KEY",
    "SN_NEWSAPI_KEY",
    "SN_TUSHARE_TOKEN",
    "SN_LOCAL_API_PROVIDER_TOKEN",
    "SN_LOCAL_API_PROVIDER_BASE_URL",
    "SN_MANAGED_PROXY_TOKEN",
    "SN_MANAGED_DATA_PROXY_TOKEN",
    "SN_MANAGED_PROXY_BASE_URL",
    "SN_MANAGED_DATA_PROXY_URL",
    "SN_BUNDLE_ALPHA_VANTAGE_KEY",
    "SN_BUNDLE_NEWSAPI_KEY",
    "SN_BUNDLE_TUSHARE_TOKEN"
  )) {
    Clear-SmokeEnvironmentValue $name
  }
  Set-SmokeEnvironmentValue "SN_DATA_DIR" $UserData
  Set-SmokeEnvironmentValue "SN_INSIGHT_DATA_DIR" $UserData
  Set-SmokeEnvironmentValue "SN_DISABLE_AUTO_SCHEDULER" "1"
  Set-SmokeEnvironmentValue "SN_LOCAL_API_PROVIDER_ENABLED" "0"
  if ($ApiPort -gt 0) {
    Set-SmokeEnvironmentValue "SN_TERMINAL_PORT" ([string]$ApiPort)
    Set-SmokeEnvironmentValue "SN_TERMINAL_API_PORT" ([string]$ApiPort)
  }
  Write-SmokeLog "Using isolated smoke data dir: $UserData"
}

function Assert-UnconfiguredSettings {
  param([object]$settingsStatus)
  Assert-True ($settingsStatus.alpha_vantage_configured -eq $false) "Alpha Vantage is unconfigured in isolated smoke"
  Assert-True ($settingsStatus.newsapi_configured -eq $false) "NewsAPI is unconfigured in isolated smoke"
  Assert-True ($settingsStatus.tushare_configured -eq $false) "Tushare is unconfigured in isolated smoke"
  Assert-True ($settingsStatus.local_api_provider_configured -eq $false) "Local API Provider is unconfigured in isolated smoke"
  Assert-True ($settingsStatus.local_api_provider_enabled -eq $false) "Local API Provider is disabled in isolated smoke"
}

function Test-IsEmptySmokeObject {
  param([object]$Value)
  if ($null -eq $Value) {
    return $true
  }
  if ($Value -is [System.Collections.IDictionary]) {
    return $Value.Count -eq 0
  }
  if ($Value -is [System.Collections.ICollection] -and -not ($Value -is [string])) {
    return $Value.Count -eq 0
  }
  $properties = @($Value | Get-Member -MemberType NoteProperty -ErrorAction SilentlyContinue)
  return $properties.Count -eq 0
}

function Assert-BlockedEmptyPredictions {
  param([object]$predictionsPayload)
  $cards = $predictionsPayload.cards
  $predictionsCount = if ($null -eq $predictionsPayload.predictions) { 0 } else { @($predictionsPayload.predictions).Count }
  Assert-True (($predictionsPayload.status -eq "blocked") -or ($predictionsCount -eq 0)) "predictions blocked or empty without provider keys"
  Assert-True ($predictionsCount -eq 0) "prediction list is empty without provider keys"
  Assert-True (Test-IsEmptySmokeObject $cards) "prediction cards are empty without provider keys"
  Assert-True ($predictionsPayload.sample_data_used -eq $false) "sample_data_used is false in installed smoke"
  Assert-True ($predictionsPayload.baseline_used -eq $false) "baseline_used is false in installed smoke"
  Assert-True ($predictionsPayload.customer_prediction_generated -eq $false) "customer_prediction_generated is false in installed smoke"
}

New-Item -ItemType Directory -Force -Path $SmokeLogDir | Out-Null
"SNInsightTerminal installed smoke started: $(Get-Date -Format s)" | Set-Content -Encoding UTF8 $ReportPath
$script:PreviousEnvironment = @{}
$process = $null
$port = 0
$shutdownAttempted = $false

try {
  Configure-IsolatedSmokeEnvironment
  Assert-True (Test-Path $SetupPath) "installer exists: $SetupPath"
  Stop-InstalledProcesses
  Seed-LegacyPrivateBundle

  if (-not $SkipInstall) {
    Write-SmokeLog "Starting silent install."
    $installArgs = @(
      "/VERYSILENT",
      "/SUPPRESSMSGBOXES",
      "/NORESTART",
      "/SP-",
      "/DIR=""$InstallDir""",
      "/LOG=""$(Join-Path $SmokeLogDir "installed_setup.log")"""
    )
    $installer = Start-Process -FilePath $SetupPath -ArgumentList $installArgs -Wait -PassThru
    Assert-True ($installer.ExitCode -eq 0) "installer exit code is 0"
    Assert-LegacyPrivateBundleRemoved
  }

  Assert-True (Test-Path $InstallDir) "install directory exists: $InstallDir"
  Assert-True (Test-Path $ExePath) "installed exe exists: $ExePath"
  if (-not $SkipInstall) {
    Assert-True (Test-Path $StartMenuShortcut) "start menu shortcut exists"
  }

  $process = Start-Process -FilePath $ExePath -ArgumentList "--no-browser" -PassThru -WindowStyle Hidden
  $ports = if ($ApiPort -gt 0) { @($ApiPort) } else { @(8765, 8766, 8767, 8768, 8769) }
  $port = Wait-TerminalPort -Ports $ports -TimeoutSeconds $TimeoutSeconds
  Write-SmokeLog "detected service port: $port"

  $docs = Invoke-SmokeRequest -Uri "http://127.0.0.1:$port/api/terminal/docs" -TimeoutSec $TimeoutSeconds
  Assert-True ($null -ne $docs) "/api/terminal/docs returns 200"
  $processStatus = Invoke-SmokeRequest -Uri "http://127.0.0.1:$port/api/terminal/system/process-status" -TimeoutSec $TimeoutSeconds
  Assert-True ([int]$processStatus.pid -eq [int]$process.Id) "process-status pid matches installed process"
  Assert-True ([int]$processStatus.port -eq [int]$port) "process-status port matches detected port"

  $dataStatus = Invoke-SmokeRequest -Uri "http://127.0.0.1:$port/api/terminal/data-status" -TimeoutSec $TimeoutSeconds
  Assert-True ($null -ne $dataStatus) "/api/terminal/data-status returns 200"
  $settingsStatus = Invoke-SmokeRequest -Uri "http://127.0.0.1:$port/api/terminal/settings/status" -TimeoutSec $TimeoutSeconds
  Assert-UnconfiguredSettings $settingsStatus
  Invoke-SmokeRequest -Uri "http://127.0.0.1:$port/api/terminal/settings/key-diagnostics" -TimeoutSec $TimeoutSeconds | Out-Null
  $predictions = Invoke-SmokeRequest -Uri "http://127.0.0.1:$port/api/terminal/predictions" -TimeoutSec $TimeoutSeconds
  Assert-BlockedEmptyPredictions $predictions

  $terminal = Invoke-SmokeWebRequest -Uri "http://127.0.0.1:$port/terminal" -TimeoutSec $TimeoutSeconds
  Assert-True ($terminal.StatusCode -eq 200) "/terminal returns 200"
  if ($terminal.Content -like "*frontend*" -and $terminal.Content -like "*npm run build*") {
    throw "/terminal still shows the missing frontend build page."
  }
  $legacy = Invoke-SmokeWebRequest -Uri "http://127.0.0.1:$port/legacy" -TimeoutSec $TimeoutSeconds
  Assert-True ($legacy.StatusCode -eq 200) "/legacy returns 200"

  if ($RunBrowserSmoke) {
    $playwrightCli = Join-Path $ProjectRoot "frontend\node_modules\@playwright\test\cli.js"
    $nodeExe = "C:\Program Files\nodejs\node.exe"
    if ((Test-Path $playwrightCli) -and (Test-Path $nodeExe)) {
      Write-SmokeLog "Starting Playwright browser smoke against installed terminal."
      Push-Location (Join-Path $ProjectRoot "frontend")
      try {
        Set-SmokeEnvironmentValue "SN_E2E_SKIP_WEBSERVER" "1"
        Set-SmokeEnvironmentValue "PLAYWRIGHT_BASE_URL" "http://127.0.0.1:$port/terminal/"
        & $nodeExe ".\node_modules\@playwright\test\cli.js" test --project=chromium
        $playwrightExitCode = $LASTEXITCODE
        Assert-True ($playwrightExitCode -eq 0) "Playwright browser smoke passed with exit code 0 (actual: $playwrightExitCode)"
      } finally {
        Pop-Location
      }
    } else {
      Write-SmokeLog "SKIP: Playwright browser smoke unavailable. Install frontend dependencies first."
    }
  }

  foreach ($dir in @("data", "cache", "logs", "reports", "models", "config", "registry", "outputs")) {
    Assert-True (Test-Path (Join-Path $UserData $dir)) "user data subdir exists: $dir"
  }
  Assert-True (Test-Path (Join-Path $UserData "config\settings.json")) "settings.json exists"
  Assert-True (Test-Path (Join-Path $UserData "config\secrets.example.json")) "secrets.example.json exists"

  $mockAlpha = "TEST_ALPHA_1234567890"
  $mockNews = "TEST_NEWS_1234567890"
  $save = Invoke-SmokeRequest -Uri "http://127.0.0.1:$port/api/terminal/settings/secrets" -Method "POST" -Body @{
    SN_ALPHA_VANTAGE_KEY = $mockAlpha
    SN_NEWSAPI_KEY = $mockNews
  } -TimeoutSec $TimeoutSeconds
  $saveText = $save | ConvertTo-Json -Depth 10
  Assert-TextNotContains -Text $saveText -Forbidden @($mockAlpha, $mockNews) -Scope "settings/secrets response"
  $secretFile = Join-Path $UserData "config\secrets.json"
  Assert-True (Test-Path $secretFile) "mock secrets.json is stored under smoke data dir"

  $reset = Invoke-SmokeRequest -Uri "http://127.0.0.1:$port/api/terminal/settings/reset" -Method "POST" -TimeoutSec $TimeoutSeconds
  $resetText = $reset | ConvertTo-Json -Depth 10
  Assert-TextNotContains -Text $resetText -Forbidden @($mockAlpha, $mockNews) -Scope "settings/reset response"
  $secretContent = if (Test-Path $secretFile) { Get-Content $secretFile -Raw } else { "" }
  Assert-TextNotContains -Text $secretContent -Forbidden @($mockAlpha, $mockNews) -Scope "secrets.json after reset"

  $logText = ""
  if (Test-Path (Join-Path $UserData "logs")) {
    Get-ChildItem (Join-Path $UserData "logs") -File -ErrorAction SilentlyContinue | ForEach-Object {
      $logText += (Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue)
    }
  }
  Assert-TextNotContains -Text $logText -Forbidden @($mockAlpha, $mockNews) -Scope "logs"

  Write-SmokeLog "Requesting backend shutdown via Terminal API."
  $shutdownAttempted = $true
  $shutdown = Invoke-SmokeRequest -Uri "http://127.0.0.1:$port/api/terminal/system/shutdown" -Method "POST" -Body @{ reason = "installed_smoke" } -TimeoutSec $TimeoutSeconds
  Assert-True ($shutdown.http_shutdown_scheduled -eq $true) "shutdown API scheduled HTTP server shutdown"
  Assert-True ($shutdown.accepting_new_tasks -eq $false) "shutdown API stopped new task acceptance"
  Assert-PortReleased -Port $port -TimeoutSeconds 20
  Stop-SmokeProcessIfRunning -Process $process -TimeoutSeconds 20
  Assert-NoSNInsightOrphanProcess

  Write-SmokeLog "Installed smoke passed."
} finally {
  if ($port -gt 0 -and -not $shutdownAttempted) {
    try {
      Write-SmokeLog "Requesting backend shutdown via Terminal API."
      $shutdownAttempted = $true
      $shutdown = Invoke-SmokeRequest -Uri "http://127.0.0.1:$port/api/terminal/system/shutdown" -Method "POST" -Body @{ reason = "installed_smoke" } -TimeoutSec 10
      Assert-True ($shutdown.http_shutdown_scheduled -eq $true) "shutdown API scheduled HTTP server shutdown"
      Assert-True ($shutdown.accepting_new_tasks -eq $false) "shutdown API stopped new task acceptance"
      Assert-PortReleased -Port $port -TimeoutSeconds 20
      Stop-SmokeProcessIfRunning -Process $process -TimeoutSeconds 20
    } catch {
      Write-SmokeLog "WARN: graceful shutdown validation failed. $($_.Exception.Message)"
    }
  }
  if ($process -and -not $process.HasExited) {
    Stop-Process -Id $process.Id -Force
  }
  Restore-SmokeEnvironment
  if ($CreatedTempDataDir -and (Test-Path $TempDataDirPath)) {
    Remove-Item -LiteralPath $TempDataDirPath -Recurse -Force -ErrorAction SilentlyContinue
    Write-SmokeLog "Removed temporary smoke data dir: $TempDataDirPath"
  }
}

if (-not $KeepInstalled) {
  $uninstaller = Get-ChildItem $InstallDir -Filter "unins*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
  Assert-True ($null -ne $uninstaller) "uninstaller exists"
  Write-SmokeLog "Starting silent uninstall."
  $uninstallProcess = Start-Process -FilePath $uninstaller.FullName -ArgumentList @(
    "/VERYSILENT",
    "/SUPPRESSMSGBOXES",
    "/NORESTART",
    "/LOG=""$(Join-Path $SmokeLogDir "installed_uninstall.log")"""
  ) -Wait -PassThru
  Assert-True ($uninstallProcess.ExitCode -eq 0) "uninstaller exit code is 0"
  Start-Sleep -Seconds 2
  Assert-True (-not (Test-Path $InstallDir)) "install directory removed after uninstall"
  if ($CreatedTempDataDir) {
    Assert-True (-not (Test-Path $TempDataDirPath)) "temporary user data directory removed after smoke"
  } else {
    Assert-True (Test-Path $UserData) "user data directory retained after uninstall"
  }
  if (Test-Path $StartMenuShortcut) {
    throw "start menu shortcut still exists after uninstall: $StartMenuShortcut"
  }
  Write-SmokeLog "Uninstall smoke passed."
}

Write-SmokeLog "SNInsightTerminal installed smoke completed."
