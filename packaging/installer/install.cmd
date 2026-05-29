@echo off
setlocal
set "APP_NAME=SN Insight Terminal"
set "APP_DIR=%LOCALAPPDATA%\Programs\SN Insight Terminal"
set "STATE_DIR=%LOCALAPPDATA%\SN Insight Terminal"
set "LOG_FILE=%STATE_DIR%\installer.log"
set "MARKER_FILE=%SN_SETUP_SMOKE_MARKER%"

if not exist "%STATE_DIR%" mkdir "%STATE_DIR%" >nul 2>nul
echo [%date% %time%] installer start >> "%LOG_FILE%"

if "%SN_SETUP_SMOKE_TEST%"=="1" (
    if "%MARKER_FILE%"=="" set "MARKER_FILE=%TEMP%\sn_setup_smoke_ok.txt"
    > "%MARKER_FILE%" echo ok %date% %time%
    echo [%date% %time%] smoke test marker written to %MARKER_FILE% >> "%LOG_FILE%"
    exit /b 0
)

if exist "%APP_DIR%\SNInsightTerminal.exe" (
    echo [%date% %time%] existing install detected, stopping running app >> "%LOG_FILE%"
    taskkill /IM SNInsightTerminal.exe /F >nul 2>nul
)

if exist "%APP_DIR%" (
    echo [%date% %time%] removing previous install folder >> "%LOG_FILE%"
    rmdir /S /Q "%APP_DIR%" >> "%LOG_FILE%" 2>&1
)

mkdir "%APP_DIR%" >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :fail

echo [%date% %time%] extracting application bundle >> "%LOG_FILE%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%~dp0app_bundle.zip' -DestinationPath '%APP_DIR%' -Force" >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :fail

copy /Y "%~dp0create_shortcuts.ps1" "%APP_DIR%\create_shortcuts.ps1" >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :fail
copy /Y "%~dp0remove_shortcuts.ps1" "%APP_DIR%\remove_shortcuts.ps1" >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :fail
copy /Y "%~dp0uninstall.cmd" "%APP_DIR%\uninstall.cmd" >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :fail

echo [%date% %time%] creating shortcuts >> "%LOG_FILE%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%APP_DIR%\create_shortcuts.ps1" "%APP_DIR%\SNInsightTerminal.exe" "%APP_DIR%\uninstall.cmd" >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :fail

if /I not "%SN_SETUP_NO_LAUNCH%"=="1" (
    echo [%date% %time%] launching application >> "%LOG_FILE%"
    start "" "%APP_DIR%\SNInsightTerminal.exe" --installed
)

echo [%date% %time%] installer complete >> "%LOG_FILE%"
exit /b 0

:fail
echo [%date% %time%] installer failed with exit code %errorlevel% >> "%LOG_FILE%"
exit /b 1
