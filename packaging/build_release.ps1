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

function Assert-NoEmbeddedPrivateBundle {
  if ($PrivateBundleKeys -or $AllowEmbeddedProviderKeys -or $RequireAllPrivateProviderKeys) {
    throw "PrivateBundleKeys 已禁用：发行包不得嵌入 provider key。请在用户本机设置页或 %LOCALAPPDATA%\SNInsightTerminal\config\secrets.json 配置密钥。"
  }
  if (Test-Path $PrivateBundleSeed) {
    Remove-Item -LiteralPath $PrivateBundleSeed -Force
    Write-Log "已删除遗留 build/private_bundle_seed.json；发行包只允许从用户本机 config\secrets.json 读取密钥。" "WARN"
  }
}

function Remove-PrivateBundleSeedSource {
  if (Test-Path $PrivateBundleSeed) {
    Remove-Item -LiteralPath $PrivateBundleSeed -Force
    Write-Log "已删除遗留 build/private_bundle_seed.json；发行包不得嵌入 private bundle seed。" "WARN"
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
    (Join-Path $DistDir "_internal\outputs"),
    (Join-Path $DistDir "_internal\cache"),
    (Join-Path $DistDir "_internal\logs"),
    (Join-Path $DistDir "_internal\private"),
    (Join-Path $DistDir "app_data"),
    (Join-Path $DistDir "outputs"),
    (Join-Path $DistDir "cache"),
    (Join-Path $DistDir "logs"),
    (Join-Path $DistDir "private")
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
        $_.Name -eq ".env.local" -or
        $_.Name -eq "secrets.json" -or
        $_.Name -eq "private_bundle_seed.json" -or
        $_.Name -eq "private_release_keys.json" -or
        $_.Extension -in @(".sqlite", ".sqlite3", ".db", ".log") -or
        $_.FullName -match "\\(app_data|outputs|cache|logs|_sn_runtime|_sn_setup_runtime)\\"
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
  if (Test-Path $PrivateBundleSeed) {
    Remove-Item -LiteralPath $PrivateBundleSeed -Force -ErrorAction SilentlyContinue
  }
  throw $failureMessage
}

Set-Content -Path $BuildLog -Value "" -Encoding UTF8
Write-Log "SNInsightTerminal 发行构建开始，版本：$Version"
Set-Location $ProjectRoot
Assert-NoEmbeddedPrivateBundle

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
