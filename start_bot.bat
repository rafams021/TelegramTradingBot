@echo off
setlocal ENABLEEXTENSIONS

rem %~dp0 = directorio donde esta este .bat (siempre termina en \)
set "BOT_DIR=%~dp0"
rem Quitar la barra final
if "%BOT_DIR:~-1%"=="\" set "BOT_DIR=%BOT_DIR:~0,-1%"

set "LOG=%BOT_DIR%\launcher.log"
echo ==== %date% %time% ==== > "%LOG%"

set "BROKER=DEMO"
echo BROKER=%BROKER%
echo BROKER=%BROKER%>>"%LOG%"
echo.

if /I "%BROKER%"=="REAL" (
    set "MT5_PATH=C:\Program Files\RoboForex MT5 Terminal\terminal64.exe"
) else (
    set "MT5_PATH=C:\Program Files\VT Markets (Pty) MT5 Terminal\terminal64.exe"
)

echo MT5_PATH=%MT5_PATH%
echo MT5_PATH=%MT5_PATH%>>"%LOG%"
echo.

if not exist "%MT5_PATH%" (
    echo ERROR: MT5 terminal not found:
    echo   "%MT5_PATH%"
    echo ERROR: MT5 terminal not found: "%MT5_PATH%">>"%LOG%"
    pause
    exit /b 1
)

echo [1/3] Starting MetaTrader 5...
echo [1/3] Starting MetaTrader 5...>>"%LOG%"
start "" "%MT5_PATH%"

echo [2/3] Waiting for MT5 to initialize...
echo [2/3] Waiting for MT5 to initialize...>>"%LOG%"
timeout /t 25 /nobreak >nul

echo [3/3] Starting TelegramTradingBot...
echo [3/3] Starting TelegramTradingBot...>>"%LOG%"

set "BOT_MAIN=%BOT_DIR%\main.py"

if not exist "%BOT_MAIN%" (
    echo ERROR: main.py not found:
    echo   "%BOT_MAIN%"
    echo ERROR: main.py not found: "%BOT_MAIN%">>"%LOG%"
    pause
    exit /b 1
)

cd /d "%BOT_DIR%"
python -u "%BOT_MAIN%"

echo.
echo Exit code: %ERRORLEVEL%
echo Exit code: %ERRORLEVEL%>>"%LOG%"
pause