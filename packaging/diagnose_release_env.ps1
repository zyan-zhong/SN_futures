$ErrorActionPreference = "Continue"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ReportPath = Join-Path $ProjectRoot "release_env_diagnosis_runtime.txt"

function Write-Report {
  param([string]$Message)
  Write-Host $Message
  Add-Content -Path $ReportPath -Value $Message -Encoding UTF8
}

function Test-ToolPath {
  param(
    [string]$Label,
    [string]$Path,
    [string[]]$Args = @("--version")
  )
  if (-not $Path) { return $false }
  if (-not (Test-Path $Path)) {
    Write-Report "  - $Label 不存在：$Path"
    return $false
  }
  try {
    $output = & $Path @Args 2>&1
    Write-Report "  - $Label 可执行：$Path -> $($output -join ' ')"
    return $true
  } catch {
    Write-Report "  - $Label 执行失败：$Path -> $($_.Exception.Message)"
    return $false
  }
}

Set-Content -Path $ReportPath -Value "" -Encoding UTF8

Write-Report "# SNInsightTerminal 发行环境诊断"
Write-Report ""
Write-Report "PowerShell 版本：$($PSVersionTable.PSVersion)"
Write-Report "当前用户：$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)"
Write-Report "项目目录：$ProjectRoot"
Write-Report ""
Write-Report "## PATH"
Write-Report $env:PATH
Write-Report ""

Write-Report "## where.exe"
# Explicit checks include: where.exe node, where.exe npm, where.exe pyinstaller, where.exe ISCC.exe.
foreach ($name in @("node", "npm", "pyinstaller", "ISCC.exe")) {
  Write-Report "### where.exe $name"
  try {
    $where = where.exe $name 2>&1
    if ($LASTEXITCODE -eq 0) { $where | ForEach-Object { Write-Report "  $_" } }
    else { Write-Report "  未找到：$($where -join ' ')" }
  } catch {
    Write-Report "  执行 where 失败：$($_.Exception.Message)"
  }
}

Write-Report ""
Write-Report "## Get-Command"
# Explicit checks include: Get-Command node, Get-Command npm, Get-Command npm.cmd, Get-Command ISCC.exe.
foreach ($name in @("node", "npm", "npm.cmd", "pyinstaller", "ISCC.exe")) {
  Write-Report "### Get-Command $name -All"
  $commands = Get-Command $name -All -ErrorAction SilentlyContinue
  if (-not $commands) { Write-Report "  未找到"; continue }
  foreach ($cmd in $commands) {
    Write-Report "  $($cmd.CommandType) $($cmd.Source)"
  }
}

Write-Report ""
Write-Report "## Node/NPM 候选路径"
$nodeCandidates = @(
  (Join-Path $env:ProgramFiles "nodejs\node.exe"),
  (Join-Path ${env:ProgramFiles(x86)} "nodejs\node.exe"),
  (Join-Path $env:LOCALAPPDATA "Programs\nodejs\node.exe"),
  (Join-Path $ProjectRoot "tools\node\node.exe"),
  (Join-Path $ProjectRoot ".tools\node\node.exe")
)
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCommand) { $nodeCandidates = @($nodeCommand.Source) + $nodeCandidates }
$nodeOk = $false
foreach ($path in ($nodeCandidates | Where-Object { $_ } | Select-Object -Unique)) {
  if (Test-ToolPath -Label "node" -Path $path -Args @("-v")) { $nodeOk = $true }
}

$npmCandidates = @(
  (Join-Path $env:ProgramFiles "nodejs\npm.cmd"),
  (Join-Path ${env:ProgramFiles(x86)} "nodejs\npm.cmd"),
  (Join-Path $env:LOCALAPPDATA "Programs\nodejs\npm.cmd"),
  (Join-Path $ProjectRoot "tools\node\npm.cmd"),
  (Join-Path $ProjectRoot ".tools\node\npm.cmd")
)
foreach ($name in @("npm.cmd", "npm")) {
  $cmd = Get-Command $name -ErrorAction SilentlyContinue
  if ($cmd) { $npmCandidates = @($cmd.Source) + $npmCandidates }
}
$npmOk = $false
foreach ($path in ($npmCandidates | Where-Object { $_ } | Select-Object -Unique)) {
  if (Test-ToolPath -Label "npm" -Path $path -Args @("-v")) { $npmOk = $true }
}

Write-Report ""
Write-Report "## PyInstaller"
try {
  $pyi = pyinstaller --version 2>&1
  Write-Report "pyinstaller --version：$($pyi -join ' ')"
} catch {
  Write-Report "pyinstaller 不可用：$($_.Exception.Message)"
}
try {
  $pyim = python -m PyInstaller --version 2>&1
  Write-Report "python -m PyInstaller --version：$($pyim -join ' ')"
} catch {
  Write-Report "python -m PyInstaller 不可用：$($_.Exception.Message)"
}

Write-Report ""
Write-Report "## Inno Setup"
$isccCandidates = @(
  (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
  (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
)
$isccCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if ($isccCommand) { $isccCandidates = @($isccCommand.Source) + $isccCandidates }
$isccOk = $false
foreach ($path in ($isccCandidates | Where-Object { $_ } | Select-Object -Unique)) {
  if (Test-ToolPath -Label "ISCC.exe" -Path $path -Args @("/?")) { $isccOk = $true }
}

Write-Report ""
Write-Report "## 建议"
if (-not $nodeOk) {
  Write-Report "- 未找到可执行 Node.js，或 node.exe 被系统策略拦截。请重新安装 Node.js LTS、修复 PATH，或使用 -NodePath 指定可用 node.exe。"
}
if (-not $npmOk) {
  Write-Report "- 未找到可执行 npm。Windows 上优先使用 npm.cmd，可用 -NpmPath 指定。"
}
if (-not $isccOk) {
  Write-Report "- 未检测到 Inno Setup。请安装 Inno Setup 6，并确认 ISCC.exe 可用。"
}
Write-Report "- 若已有 frontend/dist，可运行 packaging/build_release.ps1 -UseExistingFrontendDist 复用已有构建产物。"
Write-Report "- 不要把旧 release/SNInsightTerminal_Setup.exe 当作新构建成功产物。"

Write-Host "发行环境诊断完成：$ReportPath"
