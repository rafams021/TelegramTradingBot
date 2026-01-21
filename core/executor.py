import time
from typing import List, Optional

import config as CFG
from core import logger
from core.models import SplitState
from core.parser import parse_signal
from core.rules import decide_execution, tp_reached
from core.state import BotState
from core.management import classify_management

from adapters import mt5_client as mt5c


def _safe_text_sample(text: str, limit: int = 300) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[:limit] + "…"


def handle_management_message(
    text: str,
    msg_id: int,
    reply_to_msg_id: Optional[int],
    state: BotState,
) -> bool:
    """
    Procesa BE/CLOSE/CLOSE_AT.
    Return True si se manejó como management.
    """
    kind, price = classify_management(text)
    if not kind:
        return False

    if not reply_to_msg_id:
        logger.log({"event": f"{kind}_IGNORED_NO_REPLY", "msg_id": msg_id})
        return True

    splits = state.get_splits(reply_to_msg_id)
    if not splits:
        logger.log({"event": f"{kind}_IGNORED_NO_SIGNAL_STATE", "msg_id": msg_id, "reply_to": reply_to_msg_id})
        return True

    # ---- BE ----
    if kind == "BE":
        logger.log({"event": "BE_DETECTED", "msg_id": msg_id, "reply_to": reply_to_msg_id})
        for s in splits:
            if s.status in ("CLOSED", "CANCELED"):
                continue
            if s.be_done:
                logger.log(
                    {
                        "event": "BE_ALREADY_DONE",
                        "signal_msg_id": reply_to_msg_id,
                        "split": s.split_index,
                        "ticket": s.position_ticket,
                    }
                )
                continue

            s.be_armed = True
            if s.be_requested_ts is None:
                s.be_requested_ts = time.time()

            logger.log(
                {
                    "event": "BE_ARMED",
                    "signal_msg_id": reply_to_msg_id,
                    "split": s.split_index,
                    "status": s.status,
                    "order_ticket": s.order_ticket,
                    "position_ticket": s.position_ticket,
                }
            )
        return True

    # ---- CLOSE ----
    if kind == "CLOSE":
        logger.log({"event": "CLOSE_DETECTED", "msg_id": msg_id, "reply_to": reply_to_msg_id})
        for s in splits:
            if s.status == "OPEN" and s.position_ticket:
                req, res = mt5c.close_position(s.position_ticket, s.side, CFG.VOLUME)
                logger.log(
                    {
                        "event": "CLOSE_MARKET_RESULT",
                        "signal_msg_id": reply_to_msg_id,
                        "split": s.split_index,
                        "ticket": s.position_ticket,
                        "result": str(res),
                    }
                )
                if res and res.retcode == 10009:
                    s.status = "CLOSED"
            elif s.status == "PENDING" and s.order_ticket:
                req, res = mt5c.cancel_order(s.order_ticket)
                logger.log(
                    {
                        "event": "PENDING_CANCELED_BY_CLOSE",
                        "signal_msg_id": reply_to_msg_id,
                        "split": s.split_index,
                        "ticket": s.order_ticket,
                        "result": str(res),
                    }
                )
                s.status = "CANCELED"
        return True

    # ---- CLOSE_AT ----
    if kind == "CLOSE_AT" and price is not None:
        logger.log({"event": "CLOSE_AT_DETECTED", "msg_id": msg_id, "reply_to": reply_to_msg_id, "target": price})
        for s in splits:
            if s.status in ("CLOSED", "CANCELED"):
                continue
            s.close_target = float(price)
            s.close_armed = True
            if s.close_requested_ts is None:
                s.close_requested_ts = time.time()

            logger.log(
                {
                    "event": "CLOSE_AT_ARMED",
                    "signal_msg_id": reply_to_msg_id,
                    "split": s.split_index,
                    "status": s.status,
                    "target": s.close_target,
                    "order_ticket": s.order_ticket,
                    "position_ticket": s.position_ticket,
                }
            )
        return True

    return True


def handle_new_signal(text: str, msg_id: int, state: BotState) -> None:
    sig = parse_signal(text, msg_id)
    if not sig:
        # ---- Robust parse failure logging ----
        logger.log(
            {
                "event": "SIGNAL_PARSE_FAILED",
                "msg_id": msg_id,
                "text": _safe_text_sample(text, 300),
            }
        )
        return

    # default SL
    if sig.sl is None:
        if sig.side == "BUY":
            sig.sl = sig.entry - CFG.DEFAULT_SL_DISTANCE
        else:
            sig.sl = sig.entry + CFG.DEFAULT_SL_DISTANCE
        logger.log({"event": "SL_ASSUMED_DEFAULT", "msg_id": msg_id, "side": sig.side, "entry": sig.entry, "sl": sig.sl})

    logger.log(
        {
            "event": "SIGNAL_PARSED",
            "msg_id": msg_id,
            "side": sig.side,
            "entry": sig.entry,
            "sl": sig.sl,
            "tps": sig.tps[: CFG.MAX_SPLITS],
        }
    )

    tps = sig.tps[: CFG.MAX_SPLITS]
    splits: List[SplitState] = []

    tick = mt5c.tick()
    current_price = tick.ask if sig.side == "BUY" else tick.bid
    mode = decide_execution(sig.side, sig.entry, current_price)

    logger.log(
        {
            "event": "EXECUTION_DECIDED",
            "msg_id": msg_id,
            "side": sig.side,
            "entry": sig.entry,
            "bid": tick.bid,
            "ask": tick.ask,
            "current_price": current_price,
            "mode": mode,
        }
    )

    for i, tp in enumerate(tps):
        if tp_reached(sig.side, tp, tick.bid, tick.ask):
            logger.log({"event": "SPLIT_SKIPPED_TP_REACHED", "msg_id": msg_id, "split": i, "tp": tp})
            continue

        s = SplitState(
            signal_msg_id=sig.message_id,
            split_index=i,
            side=sig.side,
            entry=sig.entry,
            tp=tp,
            sl=float(sig.sl),
            status="NEW",
            created_ts=time.time(),
        )
        splits.append(s)

        if mode == "MARKET":
            req, res = mt5c.send_market(sig.side, CFG.VOLUME, sig.sl, tp)
            logger.log(
                {
                    "event": "OPEN_MARKET",
                    "signal_msg_id": msg_id,
                    "split": i,
                    "side": sig.side,
                    "entry": sig.entry,
                    "sl": sig.sl,
                    "tp": tp,
                    "result": str(res),
                }
            )
            if res and res.retcode == 10009:
                s.status = "OPEN"
                s.position_ticket = res.order
                try:
                    s.open_price = float(getattr(res, "price", 0.0) or req.get("price") or sig.entry)
                except Exception:
                    s.open_price = sig.entry

        else:
            req, res = mt5c.send_pending(sig.side, mode, sig.entry, CFG.VOLUME, sig.sl, tp)
            logger.log(
                {
                    "event": "OPEN_PENDING",
                    "signal_msg_id": msg_id,
                    "split": i,
                    "side": sig.side,
                    "entry": sig.entry,
                    "sl": sig.sl,
                    "tp": tp,
                    "mode": mode,
                    "result": str(res),
                }
            )
            if res and res.retcode == 10009:
                s.status = "PENDING"
                s.order_ticket = res.order

    state.set_splits(msg_id, splits)


def handle_telegram_message(text: str, msg_id: int, reply_to_msg_id: Optional[int], state: BotState) -> None:
    t = (text or "").strip()

    # 1) Management by reply
    if handle_management_message(t, msg_id, reply_to_msg_id, state):
        return

    # 2) Otherwise, trading signal
    handle_new_signal(t, msg_id, state)


