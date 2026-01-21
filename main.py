import asyncio
from telethon import TelegramClient, events

import config as CFG
from core import logger
from core.state import BotState
from core.executor import handle_telegram_message
from core.watcher import run_watcher

from adapters import mt5_client as mt5c


def _safe_text_sample(text: str, limit: int = 300) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[:limit] + "…"


async def main():
    mt5c.init()
    acc = mt5c.account_info()
    print("MT5:", acc.login, acc.server, acc.balance)
    logger.log({"event": "MT5_READY", "login": acc.login, "server": acc.server, "balance": acc.balance})

    state = BotState()

    client = TelegramClient(CFG.SESSION_NAME, CFG.API_ID, CFG.API_HASH)
    await client.start()
    me = await client.get_me()
    print("Telegram OK:", me.id)
    logger.log({"event": "TG_READY", "user_id": me.id, "channel_id": CFG.CHANNEL_ID})

    @client.on(events.NewMessage(chats=CFG.CHANNEL_ID))
    async def handler(event):
        text = (event.message.message or "").strip()
        msg_id = event.message.id
        reply_to = event.message.reply_to_msg_id
        dt = getattr(event.message, "date", None)

        # ---- Robust Telegram raw message log ----
        logger.log(
            {
                "event": "TG_MESSAGE",
                "msg_id": msg_id,
                "reply_to": reply_to,
                "date": dt.isoformat() if dt else None,
                "text": _safe_text_sample(text, 300),
            }
        )

        handle_telegram_message(text=text, msg_id=msg_id, reply_to_msg_id=reply_to, state=state)

    asyncio.create_task(run_watcher(state))
    print("Bot corriendo...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())


