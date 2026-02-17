# main.py
"""
Punto de entrada principal del TelegramTradingBot.

FASE A: Instancia MT5 única + modo degradado
FIX: Verifica sesión Telegram antes de conectar
FASE AUTONOMOUS: AutonomousTrader reemplaza _run_degraded()
FIX SYNC: Sincroniza posiciones existentes al arrancar para evitar
          re-entrada en breakouts activos tras reinicio.
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
from core.models import Signal
from core.watcher import run_watcher
from core.state import BOT_STATE


def _telegram_session_exists() -> bool:
    session_file = f"{CFG.SESSION_NAME}.session"
    exists = os.path.isfile(session_file)
    if not exists:
        get_logger().event(
            "TG_SESSION_NOT_FOUND",
            session_file=session_file,
            detail="Saltando Telegram — no hay sesión guardada.",
        )
    return exists


def _sync_existing_positions(mt5_client: MT5Client) -> None:
    """
    Sincroniza posiciones abiertas en MT5 con el BotState.

    Al arrancar, el BotState está vacío. Si hay posiciones abiertas
    con nuestro MAGIC, las registramos como señales ya ejecutadas
    para que el guard de duplicados bloquee re-entradas.

    Esto evita que el bot abra nuevas posiciones al reiniciar
    durante un breakout activo que ya tiene posiciones abiertas.
    """
    logger = get_logger()

    try:
        existing = mt5_client.get_all_positions()
    except Exception as ex:
        logger.error("SYNC_POSITIONS_ERROR", error=str(ex))
        return

    if not existing:
        logger.event("SYNC_POSITIONS_NONE")
        return

    # Agrupar por magic_comment o usar ticket como msg_id único
    # Registramos una señal sintética por cada posición para
    # que has_signal() devuelva True y bloquee duplicados
    registered = set()
    for pos in existing:
        # Usar el ticket como identificador único de la señal
        # Esto es suficiente para bloquear re-entradas
        ticket = int(getattr(pos, "ticket", 0) or 0)
        if ticket <= 0 or ticket in registered:
            continue

        # Crear señal sintética mínima para registrar en BotState
        try:
            side = "BUY" if int(getattr(pos, "type", 1)) == 0 else "SELL"
            entry = float(getattr(pos, "price_open", 0) or 0)
            sl = float(getattr(pos, "sl", 0) or 0)
            tp = float(getattr(pos, "tp", 0) or 0)

            # Si no hay SL/TP válidos, usar valores sintéticos
            if sl <= 0:
                sl = entry * 0.99 if side == "BUY" else entry * 1.01
            if tp <= 0:
                tp = entry * 1.01 if side == "BUY" else entry * 0.99

            synthetic_signal = Signal(
                message_id=ticket,
                symbol=str(getattr(pos, "symbol", CFG.SYMBOL)),
                side=side,
                entry=entry,
                tps=[tp],
                sl=sl,
            )
            BOT_STATE.add_signal(synthetic_signal)
            registered.add(ticket)

        except Exception as ex:
            logger.error(
                "SYNC_POSITION_REGISTER_ERROR",
                ticket=ticket,
                error=str(ex),
            )

    logger.event(
        "SYNC_POSITIONS_DONE",
        positions_found=len(existing),
        registered=len(registered),
    )


async def _run_telegram(tg_client: TelegramBotClient, logger) -> None:
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
        )
    finally:
        try:
            await tg_client.disconnect()
        except Exception:
            pass


async def main():
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
    # 4. SINCRONIZAR POSICIONES EXISTENTES
    # Debe correr ANTES de iniciar el trader
    # autónomo para que el guard de duplicados
    # funcione desde el primer scan.
    # ==========================================
    _sync_existing_positions(mt5_client)

    # ==========================================
    # 5. INICIAR WATCHERS
    # ==========================================
    asyncio.create_task(run_watcher(BOT_STATE))
    logger.event("WATCHERS_STARTED")

    # ==========================================
    # 6. INICIAR TRADER AUTÓNOMO
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
    # 7. TELEGRAM (opcional)
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