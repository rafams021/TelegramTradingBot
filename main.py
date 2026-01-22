# main.py
import asyncio
import traceback
from telethon import TelegramClient, events

import config as CFG
import core.logger as logger

from adapters import mt5_client as mt5c
from core.executor import execute_signal
from core.watcher import run_watcher


async def main():
    logger.log_event({
        "event": "BOOT",
        "ts": logger.iso_now(),
    })

    # MT5 init
    ok = mt5c.init()
    logger.log_event({
        "event": "MT5_READY" if ok else "MT5_INIT_FAILED",
        "login": getattr(CFG, "MT5_LOGIN", None),
        "server": getattr(CFG, "MT5_SERVER", None),
        "ts": logger.iso_now(),
    })
    if not ok:
        return

    # Telegram init
    client = TelegramClient(CFG.SESSION_NAME, CFG.API_ID, CFG.API_HASH)
    await client.start()

    logger.log_event({
        "event": "TG_READY",
        "user_id": str(getattr(client, "_self_id", "unknown")),
        "channel_id": CFG.CHANNEL_ID,
        "ts": logger.iso_now(),
    })

    # Start watcher task (BE pending, pending cancel checks, etc.)
    asyncio.create_task(run_watcher())

    @client.on(events.NewMessage(chats=CFG.CHANNEL_ID))
    async def on_message(event):
        try:
            msg = event.message
            text = msg.message or ""
            reply_to = msg.reply_to_msg_id if msg.reply_to else None

            logger.log_event({
                "event": "TG_MESSAGE",
                "msg_id": msg.id,
                "reply_to": reply_to,
                "date": msg.date.isoformat() if msg.date else None,
                "text": text,
                "ts": logger.iso_now(),
            })

            await execute_signal(
                msg_id=msg.id,
                text=text,
                reply_to=reply_to,
                date_iso=msg.date.isoformat() if msg.date else None,
            )

        except Exception as e:
            logger.log_event({
                "event": "TG_HANDLER_ERROR",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "ts": logger.iso_now(),
            })

    # (Opcional) Re-procesar edits rápidos (para casos BIU->BUY o cambios de texto)
    @client.on(events.MessageEdited(chats=CFG.CHANNEL_ID))
    async def on_message_edited(event):
        try:
            msg = event.message
            text = msg.message or ""
            reply_to = msg.reply_to_msg_id if msg.reply_to else None

            logger.log_event({
                "event": "TG_MESSAGE_EDITED",
                "msg_id": msg.id,
                "reply_to": reply_to,
                "date": msg.date.isoformat() if msg.date else None,
                "text": text,
                "ts": logger.iso_now(),
            })

            # Reprocesa: el executor/state pueden decidir ignorar si ya fue procesado
            await execute_signal(
                msg_id=msg.id,
                text=text,
                reply_to=reply_to,
                date_iso=msg.date.isoformat() if msg.date else None,
                is_edit=True,
            )

        except Exception as e:
            logger.log_event({
                "event": "TG_EDIT_HANDLER_ERROR",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "ts": logger.iso_now(),
            })

    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.log_event({
            "event": "FATAL",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "ts": logger.iso_now(),
        })
        raise




