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

Write-Host "执行 TypeScript 类型检查..." -ForegroundColor Cyan
npm run typecheck

Write-Host "构建专业前端..." -ForegroundColor Cyan
npm run build

Write-Host "frontend/dist 已生成。启动后端后可访问 http://127.0.0.1:8765/terminal" -ForegroundColor Green
