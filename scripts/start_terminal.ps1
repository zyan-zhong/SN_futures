Write-Host "SNInsightTerminal 专业终端启动指南" -ForegroundColor Cyan
Write-Host ""
Write-Host "推荐顺序："
Write-Host "1. 构建前端：   .\scripts\build_frontend.ps1"
Write-Host "2. 启动后端：   .\scripts\start_backend.ps1"
Write-Host "3. 打开浏览器： http://127.0.0.1:8765/terminal"
Write-Host ""
Write-Host "如果暂时无法使用 Node/npm，也可以直接启动后端并访问 /terminal，系统会显示中文构建提示页。"
Write-Host "旧 UI 仍可访问： http://127.0.0.1:8765/legacy"
