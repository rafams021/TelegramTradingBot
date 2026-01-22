import asyncio
from telethon import TelegramClient, events

import config as CFG
from adapters import mt5_client as mt5c
from core import logger
from core.executor import handle_signal
from core.management import classify_management
from core.state import BOT_STATE
from core.watcher import run_watcher
from core.utils import safe_text_sample


async def main():
    # MT5 init
    ok = mt5c.init()
    if not ok:
        logger.log({"event": "MT5_INIT_FAILED"})
        return
    logger.log(
        {
            "event": "MT5_READY",
            "login": mt5c.account_login(),
            "server": mt5c.account_server(),
            "balance": mt5c.account_balance(),
        }
    )

    # Telegram init
    tg = TelegramClient(CFG.SESSION_NAME, CFG.API_ID, CFG.API_HASH)
    await tg.start()
    logger.log({"event": "TG_READY", "user_id": "unknown", "channel_id": CFG.CHANNEL_ID})

    # Start watcher (BE pending, pending fills, etc.)
    asyncio.create_task(run_watcher(BOT_STATE))

    @tg.on(events.NewMessage(chats=CFG.CHANNEL_ID))
    async def on_message(event):
        msg = event.message
        text = msg.message or ""
        reply_to = msg.reply_to_msg_id if msg.reply_to else None

        logger.log(
            {
                "event": "TG_MESSAGE",
                "msg_id": msg.id,
                "reply_to": reply_to,
                "date": msg.date.isoformat() if msg.date else None,
                "text": safe_text_sample(text, 300),
            }
        )

        # 1) Management messages (BE / CLOSE / etc)
        mg = classify_management(text)
        if mg.kind != "NONE":
            # management is handled by watcher (armed flags)
            # but we need to link mg to state here
            from core.management import apply_management

            apply_management(BOT_STATE, msg_id=msg.id, reply_to=reply_to, mg=mg)
            return

        # 2) Signal messages
        await handle_signal(BOT_STATE, msg_id=msg.id, text=text)

    await tg.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())



