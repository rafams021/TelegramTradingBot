@echo off
setlocal

echo [1/3] Starting MetaTrader 5...
start "" "C:\Program Files\VT Markets (Pty) MT5 Terminal\terminal64.exe"

echo [2/3] Waiting for MT5 to initialize...
timeout /t 25 /nobreak >nul

echo [3/3] Starting TelegramTradingBot...
cd /d "C:\Users\Robo\TelegramTradingBot"

python -u "C:\Users\Robo\TelegramTradingBot\main.py" 1>>stdout.log 2>>stderr.log

echo.
echo Bot finished (or crashed). Check:
echo   - bot_events.jsonl
echo   - stderr.log
pause
