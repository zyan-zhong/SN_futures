param(
  [switch]$SkipFrontendBuild,
  [switch]$UseExistingFrontendDist,
  [string]$NodePath = "",
  [string]$NpmPath = "",
  [switch]$SkipInstaller,
  [switch]$SkipSmoke,
  [string]$Version = "0.4.3-private-research-beta.1",
  [switch]$CleanRelease,
  [switch]$PrivateBundleKeys,
  [string]$PrivateKeysFile = "packaging/private_release_keys.json",
  [switch]$AllowEmbeddedProviderKeys,
  [switch]$RequireAllPrivateProviderKeys
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ReleaseDir = Join-Path $ProjectRoot "release"
$BuildDir = Join-Path $ProjectRoot "build\SNInsightTerminal"
$DistDir = Join-Path $ProjectRoot "dist\SNInsightTerminal"
$DistExe = Join-Path $ProjectRoot "dist\SNInsightTerminal\SNInsightTerminal.exe"
$FrontendIndex = Join-Path $ProjectRoot "frontend\dist\index.html"
$BuildLog = Join-Path $ProjectRoot "release_build_log.txt"
$PrivateBundleSeed = Join-Path $ProjectRoot "build\private_bundle_seed.json"

function Write-Log {
  param([string]$Message, [string]$Level = "INFO")
  $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [$Level] $Message"
  Write-Host $line
  Add-Content -Path $BuildLog -Value $line -Encoding UTF8
}

function Test-Executable {
  param([string]$Path, [string[]]$ToolArgs = @("--version"))
  try {
    $output = & $Path @ToolArgs 2>&1
    if ($LASTEXITCODE -eq 0 -or $null -ne $output) {
      return @{ ok = $true; output = ($output -join "`n") }
    }
    return @{ ok = $false; output = "退出码 $LASTEXITCODE" }
  } catch {
    return @{ ok = $false; output = $_.Exception.Message }
  }
}

function Mask-Key {
  param([string]$Value)
  if (-not $Value) { return "" }
  $text = [string]$Value
  if ($text.Length -le 8) { return "***" }
  return "$($text.Substring(0,2))***$($text.Substring($text.Length - 2))"
}

function Read-PrivateReleaseKeys {
  param([string]$Path)
  $fileKeys = @{}
  $resolved = if ([System.IO.Path]::IsPathRooted($Path)) { $Path } else { Join-Path $ProjectRoot $Path }
  if (Test-Path $resolved) {
    $payload = Get-Content -LiteralPath $resolved -Raw | ConvertFrom-Json
    $source = $payload
    if ($payload.PSObject.Properties.Name -contains "secrets") {
      $source = $payload.secrets
    }
    foreach ($name in @("SN_ALPHA_VANTAGE_KEY", "SN_NEWSAPI_KEY", "SN_TUSHARE_TOKEN", "SN_MANAGED_PROXY_TOKEN", "SN_MANAGED_DATA_PROXY_TOKEN")) {
      if ($source.PSObject.Properties.Name -contains $name) {
        $fileKeys[$name] = [string]$source.$name
      }
    }
  } else {
    Write-Log "Private keys file not found: $Path" "WARN"
  }

  $alpha = [string]($env:SN_BUNDLE_ALPHA_VANTAGE_KEY)
  if (-not $alpha) { $alpha = [string]($env:SN_ALPHA_VANTAGE_KEY) }
  if (-not $alpha) { $alpha = [string]$fileKeys["SN_ALPHA_VANTAGE_KEY"] }

  $news = [string]($env:SN_BUNDLE_NEWSAPI_KEY)
  if (-not $news) { $news = [string]($env:SN_NEWSAPI_KEY) }
  if (-not $news) { $news = [string]$fileKeys["SN_NEWSAPI_KEY"] }

  $tushare = [string]($env:SN_BUNDLE_TUSHARE_TOKEN)
  if (-not $tushare) { $tushare = [string]($env:SN_TUSHARE_TOKEN) }
  if (-not $tushare) { $tushare = [string]$fileKeys["SN_TUSHARE_TOKEN"] }

  $managedProxy = [string]($env:SN_BUNDLE_MANAGED_PROXY_TOKEN)
  if (-not $managedProxy) { $managedProxy = [string]($env:SN_MANAGED_PROXY_TOKEN) }
  if (-not $managedProxy) { $managedProxy = [string]($env:SN_MANAGED_DATA_PROXY_TOKEN) }
  if (-not $managedProxy) { $managedProxy = [string]$fileKeys["SN_MANAGED_PROXY_TOKEN"] }
  if (-not $managedProxy) { $managedProxy = [string]$fileKeys["SN_MANAGED_DATA_PROXY_TOKEN"] }

  $missingRequired = @()
  if (-not $alpha) { $missingRequired += "Alpha Vantage" }
  if (-not $news) { $missingRequired += "NewsAPI" }
  if (-not $tushare) { $missingRequired += "Tushare" }
  if ($missingRequired.Count -gt 0) {
    $message = "PrivateBundleKeys 缺少 provider key: $($missingRequired -join ', ')。请设置 SN_BUNDLE_* 环境变量或提供 -PrivateKeysFile。"
    if ($RequireAllPrivateProviderKeys) {
      throw $message
    }
    Write-Log $message "WARN"
  }
  if (-not $managedProxy) {
    Write-Log "Managed proxy token not embedded; managed proxy remains disabled unless configured by user." "WARN"
  }
  return @{ alpha = $alpha.Trim(); news = $news.Trim(); tushare = $tushare.Trim(); managedProxy = $managedProxy.Trim() }
}

function New-PrivateBundleSeed {
  if (-not $PrivateBundleKeys) {
    if (Test-Path $PrivateBundleSeed) {
      Remove-Item -LiteralPath $PrivateBundleSeed -Force
    }
    return
  }
  if (-not $AllowEmbeddedProviderKeys) {
    throw "PrivateBundleKeys 需要显式传入 -AllowEmbeddedProviderKeys，确认这是私有/offline release bundle。"
  }
  $keys = Read-PrivateReleaseKeys -Path $PrivateKeysFile
  $payload = [ordered]@{
    schema_version = 1
    source = "private_bundle"
    created_at = (Get-Date).ToString("s")
    secrets = [ordered]@{}
  }
  if ($keys.alpha) {
    $payload.secrets["SN_ALPHA_VANTAGE_KEY"] = $keys.alpha
  }
  if ($keys.news) {
    $payload.secrets["SN_NEWSAPI_KEY"] = $keys.news
  }
  if ($keys.tushare) {
    $payload.secrets["SN_TUSHARE_TOKEN"] = $keys.tushare
  }
  if ($keys.managedProxy) {
    $payload.secrets["SN_MANAGED_DATA_PROXY_TOKEN"] = $keys.managedProxy
  }
  $dir = Split-Path -Parent $PrivateBundleSeed
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  $payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $PrivateBundleSeed -Encoding UTF8
  $alphaLog = if ($keys.alpha) { "Alpha Vantage configured ($(Mask-Key $keys.alpha))" } else { "Alpha Vantage missing" }
  $newsLog = if ($keys.news) { "NewsAPI configured ($(Mask-Key $keys.news))" } else { "NewsAPI missing" }
  $tushareLog = if ($keys.tushare) { "Tushare configured ($(Mask-Key $keys.tushare))" } else { "Tushare missing" }
  $managedLog = if ($keys.managedProxy) { "Managed proxy configured ($(Mask-Key $keys.managedProxy))" } else { "Managed proxy not embedded" }
  Write-Log "Private bundle keys enabled: $alphaLog; $newsLog; $tushareLog; $managedLog."
}

function Remove-PrivateBundleSeedSource {
  if (Test-Path $PrivateBundleSeed) {
    Remove-Item -LiteralPath $PrivateBundleSeed -Force
    Write-Log "已删除 build/private_bundle_seed.json 明文源文件；仅保留 PyInstaller bundle 内部副本。"
  }
}

function Resolve-NodeTool {
  param([string]$ExplicitPath = "")
  $candidates = @()
  if ($ExplicitPath) { $candidates += $ExplicitPath }
  $cmd = Get-Command node -ErrorAction SilentlyContinue
  if ($cmd) { $candidates += $cmd.Source }
  $candidates += @(
    (Join-Path $env:ProgramFiles "nodejs\node.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "nodejs\node.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\nodejs\node.exe"),
    (Join-Path $ProjectRoot "tools\node\node.exe"),
    (Join-Path $ProjectRoot ".tools\node\node.exe")
  )
  foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
    if (-not (Test-Path $candidate)) { continue }
    $test = Test-Executable -Path $candidate -ToolArgs @("-v")
    if ($test.ok) {
      Write-Log "Node 可用：$candidate ($($test.output))"
      return $candidate
    }
    Write-Log "Node 不可用：$candidate；原因：$($test.output)" "WARN"
  }
  throw "未找到可用 Node.js。请安装 Node.js LTS、修复 PATH，或通过 -NodePath 指定 node.exe。"
}

function Resolve-NpmTool {
  param([string]$ExplicitPath = "")
  $candidates = @()
  if ($ExplicitPath) { $candidates += $ExplicitPath }
  foreach ($name in @("npm.cmd", "npm")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { $candidates += $cmd.Source }
  }
  $candidates += @(
    (Join-Path $env:ProgramFiles "nodejs\npm.cmd"),
    (Join-Path ${env:ProgramFiles(x86)} "nodejs\npm.cmd"),
    (Join-Path $env:LOCALAPPDATA "Programs\nodejs\npm.cmd"),
    (Join-Path $ProjectRoot "tools\node\npm.cmd"),
    (Join-Path $ProjectRoot ".tools\node\npm.cmd")
  )
  foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
    if (-not (Test-Path $candidate)) { continue }
    $test = Test-Executable -Path $candidate -ToolArgs @("-v")
    if ($test.ok) {
      Write-Log "npm 可用：$candidate ($($test.output))"
      return $candidate
    }
    Write-Log "npm 不可用：$candidate；原因：$($test.output)" "WARN"
  }
  throw "未找到可用 npm。请安装 Node.js LTS、修复 PATH，或通过 -NpmPath 指定 npm.cmd。"
}

function Resolve-PyInstaller {
  $cmd = Get-Command pyinstaller -ErrorAction SilentlyContinue
  if ($cmd) {
    Write-Log "PyInstaller 可用：$($cmd.Source)"
    return @{ mode = "command"; value = $cmd.Source }
  }
  $test = Test-Executable -Path "python" -ToolArgs @("-m", "PyInstaller", "--version")
  if ($test.ok) {
    Write-Log "PyInstaller 可通过 python -m PyInstaller 使用：$($test.output)"
    return @{ mode = "module"; value = "python" }
  }
  throw "未检测到 PyInstaller。请执行 pip install pyinstaller。"
}

function Resolve-ISCC {
  $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
  if ($cmd) {
    Write-Log "Inno Setup 可用：$($cmd.Source)"
    return $cmd.Source
  }
  $candidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
  )
  foreach ($candidate in $candidates) {
    if (Test-Path $candidate) {
      Write-Log "Inno Setup 可用：$candidate"
      return $candidate
    }
  }
  throw "未检测到 Inno Setup ISCC.exe。请安装 Inno Setup 6，或把 ISCC.exe 加入 PATH。"
}

function Invoke-PyInstaller {
  param([hashtable]$Tool)
  # Equivalent command when pyinstaller is on PATH:
  # pyinstaller packaging/SNInsightTerminal.spec --clean --noconfirm
  if ($Tool.mode -eq "module") {
    & $Tool.value -m PyInstaller packaging/SNInsightTerminal.spec --clean --noconfirm
  } else {
    & $Tool.value packaging/SNInsightTerminal.spec --clean --noconfirm
  }
}

function Remove-RuntimeDataFromDist {
  $runtimeDirs = @(
    (Join-Path $DistDir "_internal\app_data"),
    (Join-Path $DistDir "app_data")
  )
  foreach ($path in $runtimeDirs) {
    if (Test-Path $path) {
      Write-Log "清理 onedir 中的运行期数据目录：$path" "WARN"
      Remove-Item -LiteralPath $path -Recurse -Force
    }
  }
}

function Assert-CleanDistForInstaller {
  $blocked = @()
  if (Test-Path $DistDir) {
    $blocked += Get-ChildItem -LiteralPath $DistDir -Recurse -Force -File -ErrorAction SilentlyContinue |
      Where-Object {
        $_.Name -eq ".env" -or
        $_.Name -eq "secrets.json" -or
        $_.Extension -in @(".sqlite", ".db") -or
        $_.FullName -match "\\app_data\\(data|cache|logs)\\"
      } |
      ForEach-Object { $_.FullName }
  }
  if ($blocked.Count -gt 0) {
    throw "onedir 输出包含不得打包的运行期/敏感文件：`n$($blocked -join "`n")"
  }
}

trap {
  $failureMessage = $_.Exception.Message
  if ($failureMessage) {
    Write-Log "发行构建失败：$failureMessage" "ERROR"
  }
  if ($PrivateBundleKeys -and (Test-Path $PrivateBundleSeed)) {
    Remove-Item -LiteralPath $PrivateBundleSeed -Force -ErrorAction SilentlyContinue
  }
  throw $failureMessage
}

Set-Content -Path $BuildLog -Value "" -Encoding UTF8
Write-Log "SNInsightTerminal 发行构建开始，版本：$Version"
Set-Location $ProjectRoot
New-PrivateBundleSeed

if ($CleanRelease -and (Test-Path $ReleaseDir)) {
  Write-Log "CleanRelease 已启用，将清理 release 目录。" "WARN"
  Remove-Item -LiteralPath $ReleaseDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null

Write-Log "运行 Python 编译和测试。"
python -m compileall -q .
if ($LASTEXITCODE -ne 0) {
  throw "python compileall failed with exit code $LASTEXITCODE"
}
pytest -q
if ($LASTEXITCODE -ne 0) {
  throw "pytest failed with exit code $LASTEXITCODE"
}

if ($UseExistingFrontendDist) {
  Write-Log "UseExistingFrontendDist 已启用：复用已有 frontend/dist，不重新构建前端。" "WARN"
  if (-not (Test-Path $FrontendIndex)) {
    throw "已请求复用 frontend/dist，但 frontend/dist/index.html 不存在。"
  }
} elseif ($SkipFrontendBuild) {
  Write-Log "SkipFrontendBuild 已启用：仅允许 dev/test 打包；正式 release 不建议使用。" "WARN"
  if (-not (Test-Path $FrontendIndex)) {
    throw "SkipFrontendBuild 要求已有 frontend/dist/index.html，否则不能继续。"
  }
} else {
  $node = Resolve-NodeTool -ExplicitPath $NodePath
  $npm = Resolve-NpmTool -ExplicitPath $NpmPath
  $nodeDir = Split-Path -Parent $node
  if ($nodeDir) {
    $env:PATH = "$nodeDir;$env:PATH"
    Write-Log "已将显式 Node 目录置于 PATH 最前：$nodeDir"
  }
  Write-Log "构建前端。"
  Push-Location "frontend"
  try {
    & $npm install
    & $npm run typecheck
    & $npm run build
    & $npm run check:ui
  } finally {
    Pop-Location
  }
  if (-not (Test-Path $FrontendIndex)) {
    throw "frontend/dist/index.html 不存在，不能生成正式发行包。"
  }
}

Write-Log "清理 PyInstaller 临时构建目录和 onedir 输出，保留 release 目录中的旧安装包。"
foreach ($path in @($BuildDir, $DistDir)) {
  if (Test-Path $path) {
    Remove-Item -LiteralPath $path -Recurse -Force
  }
}

$pyinstaller = Resolve-PyInstaller
Write-Log "运行 PyInstaller。"
Invoke-PyInstaller -Tool $pyinstaller
if (-not (Test-Path $DistExe)) {
  throw "PyInstaller 输出不存在：$DistExe"
}
Remove-PrivateBundleSeedSource

if (-not $SkipSmoke) {
  Write-Log "运行 onedir smoke。"
  $process = Start-Process -FilePath $DistExe -ArgumentList "--no-browser" -PassThru -WindowStyle Hidden
  try {
    Start-Sleep -Seconds 8
    Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/terminal/docs" -TimeoutSec 10 | Out-Null
    Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8765/terminal" -TimeoutSec 10 | Out-Null
  } finally {
    if ($process -and -not $process.HasExited) {
      Stop-Process -Id $process.Id -Force
    }
  }
} else {
  Write-Log "SkipSmoke 已启用：跳过 onedir smoke。" "WARN"
}

Remove-RuntimeDataFromDist
Assert-CleanDistForInstaller

if (-not $SkipInstaller) {
  $iscc = Resolve-ISCC
  Write-Log "运行 Inno Setup。"
  & $iscc "packaging\SNInsightTerminal.iss"
  $setup = Join-Path $ReleaseDir "SNInsightTerminal_Setup.exe"
  if (-not (Test-Path $setup)) {
    throw "安装包不存在：$setup"
  }
  Get-FileHash $setup -Algorithm SHA256 | ForEach-Object {
    "$($_.Hash)  SNInsightTerminal_Setup.exe"
  } | Set-Content -Encoding UTF8 (Join-Path $ReleaseDir "SHA256SUMS.txt")
  Write-Log "发行构建完成：$setup"
} else {
  Write-Log "SkipInstaller 已启用：未生成 Inno 安装包。" "WARN"
}
