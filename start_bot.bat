@echo off
setlocal ENABLEEXTENSIONS

REM =========================
REM Broker selector
REM =========================
REM DEMO = VT Markets
REM REAL = RoboForex
set BROKER=DEMO

if "%BROKER%"=="REAL" (
    set MT5_PATH=C:\Program Files\RoboForex MT5 Terminal\terminal64.exe
) else (
    set MT5_PATH=C:\Program Files\VT Markets (Pty) MT5 Terminal\terminal64.exe
)

echo Using broker: %BROKER%
echo MT5 path: %MT5_PATH%
echo.

REM =========================
REM Start MetaTrader 5
REM =========================
echo [1/3] Starting MetaTrader 5...
start "" "%MT5_PATH%"

echo [2/3] Waiting for MT5 to initialize...
timeout /t 25 /nobreak >nul

REM =========================
REM Start TelegramTradingBot
REM =========================
echo [3/3] Starting TelegramTradingBot...
cd /d "C:\Users\Robo\TelegramTradingBot"

python -u "C:\Users\Robo\TelegramTradingBot\main.py" ^
    1>>stdout.log ^
    2>>stderr.log

echo.
echo Bot finished (or crashed). Check:
echo   - bot_events.jsonl
echo   - stdout.log
echo   - stderr.log
pause