# main.py
import asyncio
from telethon import TelegramClient, events

import config
import core.logger as logger

from core.parser import parse_signal
from core.executor import execute_signal
from core.management import classify_management, apply_management
from core.state import BOT_STATE
from core.watcher import run_watcher
from core.mt5_client import mt5_init


def _safe_text(msg) -> str:
    try:
        return (msg.message or "").strip()
    except Exception:
        return ""


async def process_telegram_message(msg, *, is_edit: bool = False) -> None:
    text = _safe_text(msg)
    reply_to = getattr(msg, "reply_to_msg_id", None)

    if is_edit:
        logger.log({"event": "TG_MESSAGE_EDITED", "msg_id": msg.id, "reply_to": reply_to, "text": text})
    else:
        logger.log({"event": "TG_MESSAGE", "msg_id": msg.id, "reply_to": reply_to, "date": str(getattr(msg, "date", None)), "text": text})

    cache = BOT_STATE.upsert_msg_cache(msg.id, text=text)

    # 1) Management (BE / CLOSE...)
    mg = classify_management(text)
    if mg.kind != "NONE":
        apply_management(BOT_STATE, msg_id=msg.id, reply_to=reply_to, mg=mg)
        return

    # 2) Signals
    sig = parse_signal(msg.id, text)
    if not sig:
        BOT_STATE.mark_parse_attempt(msg.id, parse_failed=True)
        logger.log({"event": "SIGNAL_PARSE_FAILED", "msg_id": msg.id, "text": text})
        return

    if BOT_STATE.has_signal(sig.message_id):
        BOT_STATE.mark_parse_attempt(msg.id, parse_failed=False)
        logger.log({"event": "SIGNAL_DUPLICATE_IGNORED", "msg_id": msg.id})
        return

    BOT_STATE.mark_parse_attempt(msg.id, parse_failed=False)
    logger.log({"event": "SIGNAL_PARSED", "msg_id": sig.message_id, "side": sig.side, "entry": sig.entry, "sl": sig.sl, "tps": sig.tps})

    await execute_signal(BOT_STATE, sig)


async def main():
    # MT5 init
    mt5_info = mt5_init()
    logger.log({"event": "MT5_READY", **mt5_info})

    client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)

    @client.on(events.NewMessage(chats=config.CHANNEL_ID))
    async def on_new(event):
        await process_telegram_message(event.message, is_edit=False)

    @client.on(events.MessageEdited(chats=config.CHANNEL_ID))
    async def on_edit(event):
        msg = event.message
        text = _safe_text(msg)

        cache = BOT_STATE.upsert_msg_cache(msg.id, text=text)
        in_window = cache.within_edit_window(config.TG_EDIT_REPROCESS_WINDOW_S)

        if cache.parse_failed and in_window and cache.parse_attempts < config.TG_EDIT_REPROCESS_MAX_ATTEMPTS:
            logger.log({"event": "TG_EDIT_REPROCESS", "msg_id": msg.id, "attempts": cache.parse_attempts, "in_window": in_window})
            await process_telegram_message(msg, is_edit=True)
        else:
            logger.log({"event": "TG_MESSAGE_EDITED_IGNORED", "msg_id": msg.id, "parse_failed": cache.parse_failed, "attempts": cache.parse_attempts, "in_window": in_window})

    await client.start()
    try:
        me = await client.get_me()
        user_id = getattr(me, "id", "unknown")
    except Exception:
        user_id = "unknown"
    logger.log({"event": "TG_READY", "user_id": user_id, "channel_id": config.CHANNEL_ID})

    # Watcher loop
    asyncio.create_task(run_watcher(BOT_STATE))

    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        # Important for .bat: this guarantees the error is in bot_events.jsonl
        logger.log({"event": "FATAL", "err": str(e)})
        raise




