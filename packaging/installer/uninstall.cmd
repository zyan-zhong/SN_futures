@echo off
setlocal
set "APP_DIR=%~dp0"

if exist "%APP_DIR%remove_shortcuts.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%APP_DIR%remove_shortcuts.ps1"
)

taskkill /IM SNInsightTerminal.exe /F >nul 2>nul
start "" /min cmd /c "timeout /t 2 /nobreak >nul & rmdir /S /Q ""%APP_DIR%"""
exit /b 0
