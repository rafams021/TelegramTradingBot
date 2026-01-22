@echo off
setlocal

echo [1/3] Starting MetaTrader 5...
start "" "C:\Program Files\VT Markets (Pty) MT5 Terminal\terminal64.exe"

echo [2/3] Waiting for MT5 to initialize...
timeout /t 25 /nobreak >nul

echo [3/3] Starting TelegramTradingBot...
cd /d "C:\Users\Robo\TelegramTradingBot"
python "C:\Users\Robo\TelegramTradingBot\main.py"

echo.
echo Bot finished (or crashed). Press any key to close.
pause >nul