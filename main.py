import asyncio, time
from typing import Dict, List
from telethon import TelegramClient, events

import config as CFG
from core import logger
from core.models import Signal, SplitState
from core.parser import parse_signal
from core.rules import decide_execution, tp_reached
from adapters import mt5_client as mt5c

signals: Dict[int, List[SplitState]] = {}

async def main():
    mt5c.init()
    acc = mt5c.account_info()
    print("MT5:", acc.login, acc.server, acc.balance)

    logger.log({"event":"MT5_READY","login":acc.login,"server":acc.server,"balance":acc.balance})

    client = TelegramClient(CFG.SESSION_NAME, CFG.API_ID, CFG.API_HASH)
    await client.start()
    me = await client.get_me()
    print("Telegram OK:", me.id)
    logger.log({"event":"TG_READY","user_id":me.id,"channel_id":CFG.CHANNEL_ID})

    @client.on(events.NewMessage(chats=CFG.CHANNEL_ID))
    async def handler(event):
        text = (event.message.message or "").strip()
        msg_id = event.message.id

        # -------- BE via reply --------
        if event.message.reply_to_msg_id and ("BE" in text.upper()):
            parent = event.message.reply_to_msg_id
            splits = signals.get(parent, [])
            logger.log({"event":"BE_DETECTED","reply_to":parent})

            for s in splits:
                if s.status=="OPEN":
                    req,res = mt5c.modify_sl(s.position_ticket, s.entry)
                    logger.log({"event":"MOVE_SL_BE","ticket":s.position_ticket,"result":str(res)})
            return

        sig = parse_signal(text, msg_id)
        if not sig:
            return

        # default SL
        if sig.sl is None:
            if sig.side=="BUY":
                sig.sl = sig.entry - CFG.DEFAULT_SL_DISTANCE
            else:
                sig.sl = sig.entry + CFG.DEFAULT_SL_DISTANCE

            logger.log({"event":"SL_ASSUMED_DEFAULT","entry":sig.entry,"sl":sig.sl})

        tps = sig.tps[:CFG.MAX_SPLITS]
        splits: List[SplitState] = []

        tick = mt5c.tick()
        current_price = tick.ask if sig.side=="BUY" else tick.bid

        mode = decide_execution(sig.side, sig.entry, current_price)

        for i,tp in enumerate(tps):
            if tp_reached(sig.side,tp,tick.bid,tick.ask):
                logger.log({"event":"SPLIT_SKIPPED_TP_REACHED","tp":tp})
                continue

            s = SplitState(sig.message_id,i,sig.entry,tp,sig.sl,"NEW",created_ts=time.time())
            splits.append(s)

            if mode=="MARKET":
                req,res = mt5c.send_market(sig.side,CFG.VOLUME,sig.sl,tp)
                if res and res.retcode==10009:
                    s.status="OPEN"
                    s.position_ticket=res.order
                logger.log({"event":"OPEN_MARKET","split":i,"result":str(res)})

            else:
                req,res = mt5c.send_pending(sig.side,mode,sig.entry,CFG.VOLUME,sig.sl,tp)
                if res and res.retcode==10009:
                    s.status="PENDING"
                    s.order_ticket=res.order
                logger.log({"event":"OPEN_PENDING","split":i,"mode":mode,"result":str(res)})

        signals[msg_id] = splits

    async def watcher():
        while True:
            await asyncio.sleep(5)
            now = time.time()
            tick = mt5c.tick()

            for msg_id,splits in list(signals.items()):
                for s in splits:
                    if s.status=="PENDING":
                        if tp_reached("BUY" if s.entry< s.tp else "SELL", s.tp, tick.bid, tick.ask):
                            mt5c.cancel_order(s.order_ticket)
                            s.status="CANCELED"
                            logger.log({"event":"PENDING_CANCELED_TP","ticket":s.order_ticket})

                        elif now - s.created_ts > CFG.PENDING_TIMEOUT_MIN*60:
                            mt5c.cancel_order(s.order_ticket)
                            s.status="CANCELED"
                            logger.log({"event":"PENDING_CANCELED_TIMEOUT","ticket":s.order_ticket})

    asyncio.create_task(watcher())
    print("Bot corriendo...")
    await client.run_until_disconnected()

if __name__=="__main__":
    asyncio.run(main())
