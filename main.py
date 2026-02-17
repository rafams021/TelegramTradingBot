# main.py
"""
Punto de entrada principal del TelegramTradingBot.

FASE A - LIMPIEZA:
- Registra instancia MT5 única en compat wrapper (evita doble conexión)
- Modo degradado: si Telegram falla, el bot continúa con MT5 + watchers activos

FIX - TELEGRAM SESSION:
- Verifica que existe el archivo de sesión antes de intentar conectar
- Si no existe, salta Telegram silenciosamente sin pedir credenciales
"""
import asyncio
import os
import traceback

import config as CFG
from infrastructure.logging import get_logger

from adapters.mt5 import MT5Client
from adapters.mt5_client_compat import set_client as set_compat_client
from adapters.telegram import TelegramBotClient
from core.executor import execute_signal, set_mt5_client
from core.watcher import run_watcher
from core.state import BOT_STATE


def _telegram_session_exists() -> bool:
    """
    Verifica si existe el archivo de sesión de Telegram.

    Telethon guarda la sesión en {SESSION_NAME}.session.
    Si no existe, intentar conectar causaría un prompt interactivo
    pidiendo número de teléfono — lo cual bloquea el bot.

    Returns:
        True si el archivo de sesión existe y podemos intentar conectar
    """
    session_file = f"{CFG.SESSION_NAME}.session"
    exists = os.path.isfile(session_file)

    logger = get_logger()
    if not exists:
        logger.event(
            "TG_SESSION_NOT_FOUND",
            session_file=session_file,
            detail="Saltando Telegram — no hay sesión guardada.",
        )
    return exists


async def _run_telegram(tg_client: TelegramBotClient, logger) -> None:
    """
    Intenta conectar y correr Telegram.
    Si falla o no hay sesión, loggea y retorna silenciosamente.
    No detiene el bot ni desconecta MT5.
    """
    try:
        if not await tg_client.start():
            logger.event(
                "TG_INIT_FAILED",
                detail="Bot continuando en modo degradado sin Telegram",
            )
            return

        async def on_message(msg_id: int, text: str, reply_to: int,
                             date_iso: str, is_edit: bool = False):
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

        logger.event("TG_RUNNING")
        await tg_client.run()

    except Exception as ex:
        logger.event(
            "TG_RUNTIME_ERROR",
            error=str(ex),
            traceback=traceback.format_exc(),
            detail="Bot continuando en modo degradado sin Telegram",
        )
    finally:
        try:
            await tg_client.disconnect()
        except Exception:
            pass


async def _run_degraded(logger) -> None:
    """
    Loop de modo degradado: mantiene el proceso vivo cuando
    Telegram no está disponible. Los watchers corren en sus
    propios threads, este loop solo evita que el proceso muera.

    Cuando se implemente el módulo autónomo, reemplazará este loop.
    """
    logger.event(
        "DEGRADED_MODE_ACTIVE",
        detail="MT5 y watchers activos. Telegram no disponible. "
               "Esperando módulo autónomo.",
    )
    while True:
        await asyncio.sleep(60)
        logger.event("DEGRADED_HEARTBEAT")


async def main():
    """
    Función principal del bot.

    Flujo:
    1. Boot
    2. Conectar MT5
    3. Registrar instancia MT5 única
    4. Iniciar watchers
    5a. Si existe sesión Telegram → intentar conectar
    5b. Si no existe sesión o falla → modo degradado
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

    # ==========================================
    # 3. REGISTRAR INSTANCIA MT5 ÚNICA
    # ==========================================
    set_compat_client(mt5_client)
    set_mt5_client(mt5_client)
    logger.event("MT5_CLIENT_REGISTERED")

    # ==========================================
    # 4. INICIAR WATCHERS
    # Arrancan siempre, con o sin Telegram.
    # ==========================================
    asyncio.create_task(run_watcher(BOT_STATE))
    logger.event("WATCHERS_STARTED")

    # ==========================================
    # 5. TELEGRAM O MODO DEGRADADO
    # ==========================================
    degraded_task = asyncio.create_task(_run_degraded(logger))

    if _telegram_session_exists():
        # Hay sesión guardada — intentar conectar
        tg_client = TelegramBotClient(
            api_id=CFG.API_ID,
            api_hash=CFG.API_HASH,
            session_name=CFG.SESSION_NAME,
            channel_id=CFG.CHANNEL_ID,
            state=BOT_STATE,
        )

        try:
            telegram_task = asyncio.create_task(
                _run_telegram(tg_client, logger)
            )
            await telegram_task

            logger.event(
                "TG_TASK_ENDED",
                detail="Telegram terminó. Bot continúa en modo degradado.",
            )
        except KeyboardInterrupt:
            raise

    # Mantener bot vivo por degraded loop
    try:
        await degraded_task
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