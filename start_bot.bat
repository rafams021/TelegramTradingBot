@echo off
setlocal ENABLEEXTENSIONS

set "LOG=%~dp0launcher.log"
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

set "BOT_DIR=C:\Users\Robo\TelegramTradingBot"
set "BOT_MAIN=%BOT_DIR%\main.py"

if not exist "%BOT_MAIN%" (
    echo ERROR: main.py not found:
    echo   "%BOT_MAIN%"
    echo ERROR: main.py not found: "%BOT_MAIN%">>"%LOG%"
    pause
    exit /b 1
)

cd /d "%BOT_DIR%"
python -u "%BOT_MAIN%" 1>>stdout.log 2>>stderr.log

echo Exit code: %ERRORLEVEL%>>"%LOG%"
pause