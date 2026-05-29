$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$env:PYTHONPATH = (Join-Path $ProjectRoot "src")

Write-Host "正在启动 SNInsightTerminal 后端 API..." -ForegroundColor Cyan
Write-Host "旧 UI: http://127.0.0.1:8765/legacy"
Write-Host "新终端: http://127.0.0.1:8765/terminal"
Write-Host "Terminal API 文档: http://127.0.0.1:8765/api/terminal/docs"
Write-Host ""

Set-Location $ProjectRoot
python app_launcher.py --api-server
