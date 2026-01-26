# main.py
import asyncio
import traceback
from telethon import TelegramClient, events

import config as CFG
import infrastructure.logging.logger as logger

try:
    from core.utils import set_tg_startup_cutoff, should_process_tg_message, safe_text_sample
except Exception:
    from utils import set_tg_startup_cutoff, should_process_tg_message, safe_text_sample

from adapters import mt5_client as mt5c
from core.executor import execute_signal
from core.watcher import run_watcher
from core.state import BOT_STATE


async def main():
    logger.log_event(
        {
            "event": "BOOT",
            "ts": logger.iso_now(),
        }
    )

    # MT5 init
    ok = mt5c.init()
    logger.log_event(
        {
            "event": "MT5_READY" if ok else "MT5_INIT_FAILED",
            "login": getattr(CFG, "MT5_LOGIN", None),
            "server": getattr(CFG, "MT5_SERVER", None),
            "ts": logger.iso_now(),
        }
    )
    if not ok:
        return

    # Telegram init
    client = TelegramClient(CFG.SESSION_NAME, CFG.API_ID, CFG.API_HASH)
    await client.start()

    logger.log_event(
        {
            "event": "TG_READY",
            "user_id": str(getattr(client, "_self_id", "unknown")),
            "channel_id": CFG.CHANNEL_ID,
            "ts": logger.iso_now(),
        }
    )

    # Safety: prevent processing Telegram "catch-up" backlog after restart.
    cutoff_iso = set_tg_startup_cutoff(BOT_STATE)
    logger.log_event(
        {
            "event": "TG_STARTUP_CUTOFF_SET",
            "cutoff": cutoff_iso,
            "ts": logger.iso_now(),
        }
    )

    # Start watcher task (BE pending, pending cancel checks, etc.)
    asyncio.create_task(run_watcher(BOT_STATE))

    @client.on(events.NewMessage(chats=CFG.CHANNEL_ID))
    async def on_message(event):
        try:
            msg = event.message
            text = msg.message or ""
            reply_to = msg.reply_to_msg_id if msg.reply_to else None

            ok, reason, cutoff_iso, age_s = should_process_tg_message(
                state=BOT_STATE,
                msg_id=msg.id,
                msg_date_iso=msg.date.isoformat() if msg.date else None,
                is_edit=False,
            )
            if not ok:
                logger.log_event(
                    {
                        "event": "TG_MESSAGE_IGNORED",
                        "msg_id": msg.id,
                        "is_edit": False,
                        "reply_to": reply_to,
                        "date": msg.date.isoformat() if msg.date else None,
                        "cutoff": cutoff_iso,
                        "age_s": age_s,
                        "reason": reason,
                        "text": safe_text_sample(text, 300),
                        "ts": logger.iso_now(),
                    }
                )
                return

            logger.log_event(
                {
                    "event": "TG_MESSAGE",
                    "msg_id": msg.id,
                    "reply_to": reply_to,
                    "date": msg.date.isoformat() if msg.date else None,
                    "text": text,
                    "ts": logger.iso_now(),
                }
            )

            await execute_signal(
                msg_id=msg.id,
                text=text,
                reply_to=reply_to,
                date_iso=msg.date.isoformat() if msg.date else None,
                state=BOT_STATE,
            )

        except Exception as e:
            logger.log_event(
                {
                    "event": "TG_HANDLER_ERROR",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "ts": logger.iso_now(),
                }
            )

    @client.on(events.MessageEdited(chats=CFG.CHANNEL_ID))
    async def on_message_edited(event):
        try:
            msg = event.message
            text = msg.message or ""
            reply_to = msg.reply_to_msg_id if msg.reply_to else None

            ok, reason, cutoff_iso, age_s = should_process_tg_message(
                state=BOT_STATE,
                msg_id=msg.id,
                msg_date_iso=msg.date.isoformat() if msg.date else None,
                is_edit=True,
            )
            if not ok:
                logger.log_event(
                    {
                        "event": "TG_MESSAGE_IGNORED",
                        "msg_id": msg.id,
                        "is_edit": True,
                        "reply_to": reply_to,
                        "date": msg.date.isoformat() if msg.date else None,
                        "cutoff": cutoff_iso,
                        "age_s": age_s,
                        "reason": reason,
                        "text": safe_text_sample(text, 300),
                        "ts": logger.iso_now(),
                    }
                )
                return

            logger.log_event(
                {
                    "event": "TG_MESSAGE_EDITED",
                    "msg_id": msg.id,
                    "reply_to": reply_to,
                    "date": msg.date.isoformat() if msg.date else None,
                    "text": text,
                    "ts": logger.iso_now(),
                }
            )

            await execute_signal(
                msg_id=msg.id,
                text=text,
                reply_to=reply_to,
                date_iso=msg.date.isoformat() if msg.date else None,
                is_edit=True,
                state=BOT_STATE,
            )

        except Exception as e:
            logger.log_event(
                {
                    "event": "TG_EDIT_HANDLER_ERROR",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "ts": logger.iso_now(),
                }
            )

    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.log_event(
            {
                "event": "FATAL",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "ts": logger.iso_now(),
            }
        )
        raise



