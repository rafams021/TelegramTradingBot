# main.py
"""
Punto de entrada principal del TelegramTradingBot.

REFACTORIZADO EN FASE 3B:
- Usa MT5Client y TelegramBotClient
- Código más limpio y organizado
- Mejor separación de responsabilidades

FIX: Establece mt5_client global para executor
"""
import asyncio
import traceback

import config as CFG
from infrastructure.logging import get_logger

from adapters.mt5 import MT5Client
from adapters.telegram import TelegramBotClient
from core.executor import execute_signal, set_mt5_client
from core.watcher import run_watcher
from core.state import BOT_STATE


async def main():
    """
    Función principal del bot.
    
    Flujo:
    1. Inicializar logger
    2. Conectar con MT5
    3. Conectar con Telegram
    4. Configurar handlers
    5. Iniciar watcher
    6. Ejecutar bot
    """
    logger = get_logger()
    
    # ==========================================
    # 1. BOOT
    # ==========================================
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
        logger.event(
            "MT5_INIT_FAILED",
            login=CFG.MT5_LOGIN,
            server=CFG.MT5_SERVER,
        )
        return
    
    logger.event(
        "MT5_READY",
        login=CFG.MT5_LOGIN,
        server=CFG.MT5_SERVER,
    )
    
    # CRITICAL: Set global MT5 client for executor
    set_mt5_client(mt5_client)
    
    # ==========================================
    # 3. TELEGRAM CONNECTION
    # ==========================================
    tg_client = TelegramBotClient(
        api_id=CFG.API_ID,
        api_hash=CFG.API_HASH,
        session_name=CFG.SESSION_NAME,
        channel_id=CFG.CHANNEL_ID,
        state=BOT_STATE,
    )
    
    if not await tg_client.start():
        logger.event("TG_INIT_FAILED")
        mt5_client.disconnect()
        return
    
    # ==========================================
    # 4. SETUP HANDLERS
    # ==========================================
    async def on_message(msg_id: int, text: str, reply_to: int, 
                        date_iso: str, is_edit: bool = False):
        """Handler para mensajes de Telegram."""
        await execute_signal(
            msg_id=msg_id,
            text=text,
            reply_to=reply_to,
            date_iso=date_iso,
            is_edit=is_edit,
            state=BOT_STATE,
        )
    
    async def on_edit(msg_id: int, text: str, reply_to: int, 
                     date_iso: str, is_edit: bool = True):
        """Handler para ediciones de mensajes."""
        await execute_signal(
            msg_id=msg_id,
            text=text,
            reply_to=reply_to,
            date_iso=date_iso,
            is_edit=is_edit,
            state=BOT_STATE,
        )
    
    tg_client.setup_handlers(
        on_message=on_message,
        on_edit=on_edit,
    )
    
    # ==========================================
    # 5. START WATCHER
    # ==========================================
    asyncio.create_task(run_watcher(BOT_STATE))
    logger.info("Watcher iniciado")
    
    # ==========================================
    # 6. RUN BOT
    # ==========================================
    logger.info("Bot iniciado correctamente")
    
    try:
        await tg_client.run()
    finally:
        # Cleanup
        await tg_client.disconnect()
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