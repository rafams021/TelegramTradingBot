# main.py
"""
TelegramTradingBot - Modo Autonomo

Bot de trading completamente autonomo.
Genera y ejecuta señales usando MarketAnalyzer y estrategias propias.

Arquitectura Dual Loop:
- Candle Loop (H1): Reversal + Trend cada 5 minutos
- Tick Loop (M1): Momentum cada 100ms

Uso:
    python main.py
"""
import asyncio
import traceback

import config as CFG
from adapters.mt5 import MT5Client
from autonomous.trader import AutonomousTrader
from autonomous.executor import set_mt5_client
from core.state import BOT_STATE
from infrastructure.logging import get_logger


async def main():
    logger = get_logger()
    logger.event("BOOT_AUTONOMOUS")

    print("=" * 70)
    print("  TRADING BOT - MODO AUTONOMO")
    print("=" * 70)
    print(f"  Symbol    : {CFG.SYMBOL}")
    print(f"  Timeframe : H1 (candle loop) + M1 (tick loop)")
    print(f"  Strategies: Reversal, Trend, Momentum")
    print("=" * 70)

    print("\nConectando a MT5...")

    mt5_client = MT5Client(
        login=CFG.MT5_LOGIN,
        password=CFG.MT5_PASSWORD,
        server=CFG.MT5_SERVER,
        symbol=CFG.SYMBOL,
        deviation=CFG.DEVIATION,
        magic=CFG.MAGIC,
        dry_run=CFG.DRY_RUN,
    )

    if not mt5_client.connect():
        print(f"Error: No se pudo conectar a MT5")
        print(f"  Login : {CFG.MT5_LOGIN}")
        print(f"  Server: {CFG.MT5_SERVER}")
        logger.event("MT5_INIT_FAILED", login=CFG.MT5_LOGIN, server=CFG.MT5_SERVER)
        return

    print(f"MT5 conectado")
    print(f"  Login : {CFG.MT5_LOGIN}")
    print(f"  Server: {CFG.MT5_SERVER}")
    print(f"  Symbol: {CFG.SYMBOL}")

    logger.event("MT5_READY", login=CFG.MT5_LOGIN, server=CFG.MT5_SERVER)

    set_mt5_client(mt5_client)

    print(f"\nIniciando Autonomous Trader...")
    print(f"  Candle Loop: Cada {CFG.SCAN_INTERVAL}s")
    print(f"  Tick Loop  : Cada 100ms")

    trader = AutonomousTrader(
        state=BOT_STATE,
        scan_interval=CFG.SCAN_INTERVAL,
        timeframe="H1",
        candles=100,
        tick_interval_ms=100,
    )

    logger.event("AUTONOMOUS_TRADER_INIT")

    print("\nBot autonomo iniciado")
    print("\n" + "=" * 70)
    print("  BOT OPERANDO - Presiona Ctrl+C para detener")
    print("=" * 70)

    try:
        await trader.run()

    except KeyboardInterrupt:
        print("\nDeteniendo bot...")
        logger.event("SHUTDOWN_REQUESTED")

    except Exception as ex:
        print(f"\nError critico: {ex}")
        logger.event(
            "AUTONOMOUS_ERROR",
            error=str(ex),
            traceback=traceback.format_exc(),
        )

    finally:
        print("Desconectando MT5...")
        mt5_client.disconnect()
        print("Bot detenido")
        logger.event("SHUTDOWN_COMPLETE")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAdios!")
