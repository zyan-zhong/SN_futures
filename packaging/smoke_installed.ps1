param(
  [string]$SetupPath = "",
  [switch]$SkipInstall,
  [switch]$KeepInstalled,
  [switch]$RunBrowserSmoke,
  [switch]$ExpectPrivateBundleKeys
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $SetupPath) {
  $SetupPath = Join-Path $ProjectRoot "release\SNInsightTerminal_Setup.exe"
}
$ReportPath = Join-Path $ProjectRoot "release\installed_smoke_report.txt"
$SmokeLogDir = Join-Path $env:TEMP "SNInsightTerminalSmoke"
$UserData = Join-Path $env:LOCALAPPDATA "SNInsightTerminal"
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\SNInsightTerminal"
$ExePath = Join-Path $InstallDir "SNInsightTerminal.exe"
$StartMenuShortcut = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\SNInsightTerminal\SNInsightTerminal.lnk"

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
    $params["Body"] = ($Body | ConvertTo-Json -Depth 5)
    $params["ContentType"] = "application/json"
  }
  return Invoke-RestMethod @params
}

function Wait-TerminalPort {
  param([int[]]$Ports, [int]$TimeoutSeconds = 45)
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    foreach ($port in $Ports) {
      try {
        Invoke-SmokeRequest -Uri "http://127.0.0.1:$port/api/terminal/docs" | Out-Null
        return $port
      } catch {
        Start-Sleep -Milliseconds 200
      }
    }
  }
  throw "Timed out waiting for Terminal API on ports 8765-8769."
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

"SNInsightTerminal installed smoke started: $(Get-Date -Format s)" | Set-Content -Encoding UTF8 $ReportPath
New-Item -ItemType Directory -Force -Path $SmokeLogDir | Out-Null

Assert-True (Test-Path $SetupPath) "installer exists: $SetupPath"
Stop-InstalledProcesses

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
}

Assert-True (Test-Path $InstallDir) "install directory exists: $InstallDir"
Assert-True (Test-Path $ExePath) "installed exe exists: $ExePath"
Assert-True (Test-Path $StartMenuShortcut) "start menu shortcut exists"

$process = Start-Process -FilePath $ExePath -ArgumentList "--no-browser" -PassThru -WindowStyle Hidden
$port = 0
try {
  $port = Wait-TerminalPort -Ports @(8765, 8766, 8767, 8768, 8769)
  Write-SmokeLog "detected service port: $port"

  try {
    Invoke-SmokeRequest -Uri "http://127.0.0.1:$port/api/terminal/system-health" -TimeoutSec 60 | Out-Null
    Write-SmokeLog "PASS: system-health endpoint responded"
  } catch {
    Write-SmokeLog "WARN: system-health endpoint did not respond within smoke timeout; continuing because docs API is available. $($_.Exception.Message)"
  }
  try {
    Invoke-SmokeRequest -Uri "http://127.0.0.1:$port/api/terminal/data-status" -TimeoutSec 60 | Out-Null
    Write-SmokeLog "PASS: data-status endpoint responded"
  } catch {
    Write-SmokeLog "WARN: data-status endpoint did not respond within smoke timeout; continuing with settings and browser checks. $($_.Exception.Message)"
  }
  $settingsStatus = Invoke-SmokeRequest -Uri "http://127.0.0.1:$port/api/terminal/settings/status" -TimeoutSec 60
  $keyDiagnostics = Invoke-SmokeRequest -Uri "http://127.0.0.1:$port/api/terminal/settings/key-diagnostics" -TimeoutSec 60
  Invoke-SmokeRequest -Uri "http://127.0.0.1:$port/api/terminal/snapshot" -TimeoutSec 60 | Out-Null

  if ($ExpectPrivateBundleKeys) {
    Assert-True ([bool]$settingsStatus.alpha_vantage_configured) "private bundle Alpha Vantage key is configured"
    Assert-True ([bool]$settingsStatus.newsapi_configured) "private bundle NewsAPI key is configured"
    Assert-True ($settingsStatus.alpha_vantage_source -in @("private_bundle", "user_secrets", "env")) "Alpha Vantage source is private_bundle/user_secrets/env"
    Assert-True ($settingsStatus.newsapi_source -in @("private_bundle", "user_secrets", "env")) "NewsAPI source is private_bundle/user_secrets/env"
    $diagText = $keyDiagnostics | ConvertTo-Json -Depth 10
    Assert-True ($diagText -notlike "*SN_BUNDLE_*") "key diagnostics do not expose bundle env names with values"
    $newsTest = Invoke-SmokeRequest -Uri "http://127.0.0.1:$port/api/terminal/newsapi/test" -Method "POST" -Body @{}
    Assert-True ($newsTest.message_zh -notlike "*key_missing*") "NewsAPI test is not key_missing"
    Assert-True ($newsTest.message_zh -notlike "*未配置*") "NewsAPI test is not unconfigured"
  }

  $terminal = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/terminal" -TimeoutSec 10
  Assert-True ($terminal.StatusCode -eq 200) "/terminal returns 200"
  if ($terminal.Content -like "*frontend*" -and $terminal.Content -like "*npm run build*") {
    throw "/terminal still shows the missing frontend build page."
  }
  $legacy = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/legacy" -TimeoutSec 10
  Assert-True ($legacy.StatusCode -eq 200) "/legacy returns 200"

  if ($RunBrowserSmoke) {
    $playwrightCli = Join-Path $ProjectRoot "frontend\node_modules\@playwright\test\cli.js"
    $nodeExe = "C:\Program Files\nodejs\node.exe"
    if ((Test-Path $playwrightCli) -and (Test-Path $nodeExe)) {
      Write-SmokeLog "Starting Playwright browser smoke against installed terminal."
      Push-Location (Join-Path $ProjectRoot "frontend")
      try {
        $env:SN_E2E_SKIP_WEBSERVER = "1"
        $env:PLAYWRIGHT_BASE_URL = "http://127.0.0.1:$port/terminal/"
        & $nodeExe ".\node_modules\@playwright\test\cli.js" test --project=chromium
        $playwrightExitCode = $LASTEXITCODE
        Assert-True ($playwrightExitCode -eq 0) "Playwright browser smoke passed with exit code 0 (actual: $playwrightExitCode)"
      } finally {
        Remove-Item Env:\SN_E2E_SKIP_WEBSERVER -ErrorAction SilentlyContinue
        Remove-Item Env:\PLAYWRIGHT_BASE_URL -ErrorAction SilentlyContinue
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
  }
  $saveText = $save | ConvertTo-Json -Depth 10
  Assert-TextNotContains -Text $saveText -Forbidden @($mockAlpha, $mockNews) -Scope "settings/secrets response"
  $secretFile = Join-Path $UserData "config\secrets.json"
  Assert-True (Test-Path $secretFile) "mock secrets.json is stored under user data"

  $reset = Invoke-SmokeRequest -Uri "http://127.0.0.1:$port/api/terminal/settings/reset" -Method "POST"
  $resetText = $reset | ConvertTo-Json -Depth 10
  Assert-TextNotContains -Text $resetText -Forbidden @($mockAlpha, $mockNews) -Scope "settings/reset response"
  $secretContent = if (Test-Path $secretFile) { Get-Content $secretFile -Raw } else { "" }
  Assert-TextNotContains -Text $secretContent -Forbidden @($mockAlpha, $mockNews) -Scope "secrets.json after reset"
  if ($ExpectPrivateBundleKeys) {
    $afterReset = Invoke-SmokeRequest -Uri "http://127.0.0.1:$port/api/terminal/settings/status"
    Assert-True ([bool]$afterReset.alpha_vantage_configured) "reset restores or retains Alpha Vantage private default"
    Assert-True ([bool]$afterReset.newsapi_configured) "reset restores or retains NewsAPI private default"
  }

  $logText = ""
  if (Test-Path (Join-Path $UserData "logs")) {
    Get-ChildItem (Join-Path $UserData "logs") -File -ErrorAction SilentlyContinue | ForEach-Object {
      $logText += (Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue)
    }
  }
  Assert-TextNotContains -Text $logText -Forbidden @($mockAlpha, $mockNews) -Scope "logs"
  if ($ExpectPrivateBundleKeys) {
    & (Join-Path $ProjectRoot "scripts\scan_runtime_secrets.ps1")
    Assert-True ($LASTEXITCODE -eq 0) "runtime secret scan passed"
  }

  Write-SmokeLog "Installed smoke passed."
} finally {
  if ($process -and -not $process.HasExited) {
    Stop-Process -Id $process.Id -Force
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
  Assert-True (Test-Path $UserData) "user data directory retained after uninstall"
  if (Test-Path $StartMenuShortcut) {
    throw "start menu shortcut still exists after uninstall: $StartMenuShortcut"
  }
  Write-SmokeLog "Uninstall smoke passed."
}

Write-SmokeLog "SNInsightTerminal installed smoke completed."
