$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$FrontendDir = Join-Path $ProjectRoot "frontend"

Write-Host "检查 Node / npm 环境..." -ForegroundColor Cyan
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
if (-not $nodeCmd -or -not $npmCmd) {
  Write-Host "未检测到可用的 node 或 npm。请先安装 Node.js LTS，或检查当前终端权限。" -ForegroundColor Yellow
  exit 1
}

Set-Location $FrontendDir
if (-not (Test-Path "node_modules")) {
  Write-Host "node_modules 不存在，正在执行 npm install..." -ForegroundColor Cyan
  npm install
}

Write-Host "启动 Vite 开发服务器: http://127.0.0.1:5173/terminal/" -ForegroundColor Green
npm run dev
