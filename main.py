# main.py
"""
Punto de entrada principal del TelegramTradingBot.

FASE A: Instancia MT5 única + modo degradado
FIX: Verifica sesión Telegram antes de conectar
FASE AUTONOMOUS: _run_degraded() reemplazado por AutonomousTrader
"""
import asyncio
import os
import traceback

import config as CFG
from infrastructure.logging import get_logger

from adapters.mt5 import MT5Client
from adapters.mt5_client_compat import set_client as set_compat_client
from adapters.telegram import TelegramBotClient
from autonomous import AutonomousTrader
from core.executor import execute_signal, set_mt5_client
from core.watcher import run_watcher
from core.state import BOT_STATE


def _telegram_session_exists() -> bool:
    """
    Verifica si existe el archivo de sesión de Telegram.
    Si no existe, conectar causaría un prompt interactivo.
    """
    session_file = f"{CFG.SESSION_NAME}.session"
    exists = os.path.isfile(session_file)
    if not exists:
        get_logger().event(
            "TG_SESSION_NOT_FOUND",
            session_file=session_file,
            detail="Saltando Telegram — no hay sesión guardada.",
        )
    return exists


async def _run_telegram(tg_client: TelegramBotClient, logger) -> None:
    """
    Intenta conectar y correr Telegram.
    Si falla, loggea y retorna silenciosamente.
    """
    try:
        if not await tg_client.start():
            logger.event(
                "TG_INIT_FAILED",
                detail="Bot continuando en modo autónomo sin Telegram",
            )
            return

        async def on_message(msg_id: int, text: str, reply_to: int,
                             date_iso: str, is_edit: bool = False):
            await execute_signal(
                msg_id=msg_id, text=text, reply_to=reply_to,
                date_iso=date_iso, is_edit=is_edit, state=BOT_STATE,
            )

        async def on_edit(msg_id: int, text: str, reply_to: int,
                          date_iso: str, is_edit: bool = True):
            await execute_signal(
                msg_id=msg_id, text=text, reply_to=reply_to,
                date_iso=date_iso, is_edit=is_edit, state=BOT_STATE,
            )

        tg_client.setup_handlers(on_message=on_message, on_edit=on_edit)
        logger.event("TG_RUNNING")
        await tg_client.run()

    except Exception as ex:
        logger.event(
            "TG_RUNTIME_ERROR",
            error=str(ex),
            traceback=traceback.format_exc(),
            detail="Bot continuando en modo autónomo sin Telegram",
        )
    finally:
        try:
            await tg_client.disconnect()
        except Exception:
            pass


async def main():
    """
    Función principal del bot.

    Flujo:
    1. Boot
    2. Conectar MT5
    3. Registrar instancia MT5 única
    4. Iniciar watchers
    5. Iniciar trader autónomo
    6. Intentar Telegram si hay sesión (opcional)
    """
    logger = get_logger()
    logger.event("BOOT")

    # ==========================================
    # 2. MT5 CONNECTION
    # ==========================================
    mt5_client = MT5Client(
        login=CFG.MT5_LOGIN,
        password=CFG.MT5_PASSWORD,
        server=CFG.MT5_SERVER,
        symbol=CFG.SYMBOL,
        deviation=getattr(CFG, "DEVIATION", 50),
        magic=getattr(CFG, "MAGIC", 0),
        dry_run=getattr(CFG, "DRY_RUN", False),
    )

    if not mt5_client.connect():
        logger.event("MT5_INIT_FAILED", login=CFG.MT5_LOGIN, server=CFG.MT5_SERVER)
        return

    logger.event("MT5_READY", login=CFG.MT5_LOGIN, server=CFG.MT5_SERVER)

    # ==========================================
    # 3. REGISTRAR INSTANCIA MT5 ÚNICA
    # ==========================================
    set_compat_client(mt5_client)
    set_mt5_client(mt5_client)
    logger.event("MT5_CLIENT_REGISTERED")

    # ==========================================
    # 4. INICIAR WATCHERS
    # ==========================================
    asyncio.create_task(run_watcher(BOT_STATE))
    logger.event("WATCHERS_STARTED")

    # ==========================================
    # 5. INICIAR TRADER AUTÓNOMO
    # ==========================================
    scan_interval = int(getattr(CFG, "SCAN_INTERVAL", 300))
    trader = AutonomousTrader(
        state=BOT_STATE,
        scan_interval=scan_interval,
        timeframe="H1",
        candles=100,
    )
    autonomous_task = asyncio.create_task(trader.run())
    logger.event("AUTONOMOUS_TRADER_TASK_STARTED", scan_interval=scan_interval)

    # ==========================================
    # 6. TELEGRAM (opcional)
    # ==========================================
    try:
        if _telegram_session_exists():
            tg_client = TelegramBotClient(
                api_id=CFG.API_ID,
                api_hash=CFG.API_HASH,
                session_name=CFG.SESSION_NAME,
                channel_id=CFG.CHANNEL_ID,
                state=BOT_STATE,
            )
            telegram_task = asyncio.create_task(
                _run_telegram(tg_client, logger)
            )
            await telegram_task
            logger.event(
                "TG_TASK_ENDED",
                detail="Telegram terminó. Bot continúa autónomo.",
            )

        # Mantener bot vivo por el trader autónomo
        await autonomous_task

    except KeyboardInterrupt:
        raise
    finally:
        mt5_client.disconnect()
        logger.event("SHUTDOWN")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Bot detenido por usuario")
    except Exception as e:
        logger = get_logger()
        logger.event(
            "FATAL",
            error=str(e),
            traceback=traceback.format_exc(),
        )
        raise