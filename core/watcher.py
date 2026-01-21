import asyncio
import time

import config as CFG
from core import logger
from core.rules import tp_reached
from core.state import BotState

from adapters import mt5_client as mt5c


def _min_stop_distance() -> float:
    c = mt5c.stop_constraints()
    point = float(c.get("point", 0.0) or 0.0)
    stops = int(c.get("stops_level_points", 0) or 0)
    freeze = int(c.get("freeze_level_points", 0) or 0)
    lvl = max(stops, freeze)
    return lvl * point + float(getattr(CFG, "BE_EXTRA_BUFFER", 0.0) or 0.0)


def _be_allowed(side: str, be_price: float, bid: float, ask: float, min_dist: float) -> bool:
    if side == "BUY":
        return (bid - be_price) >= min_dist
    else:
        return (be_price - ask) >= min_dist


def _close_at_triggered(side: str, target: float, bid: float, ask: float) -> bool:
    buf = float(getattr(CFG, "CLOSE_AT_BUFFER", 0.0) or 0.0)
    if side == "BUY":
        return bid >= (target + buf)
    else:
        return ask <= (target - buf)


def _try_attach_filled_position(s, open_positions) -> bool:
    match = None
    for p in open_positions:
        try:
            if float(getattr(p, "tp", 0.0) or 0.0) != float(s.tp):
                continue
            if float(getattr(p, "sl", 0.0) or 0.0) != float(s.sl):
                continue
        except Exception:
            continue

        p_side = "BUY" if int(getattr(p, "type", 0)) == 0 else "SELL"
        if p_side != s.side:
            continue

        try:
            if abs(float(getattr(p, "price_open", 0.0) or 0.0) - float(s.entry)) > 5.0:
                continue
        except Exception:
            continue

        match = p
        break

    if match is None:
        return False

    s.status = "OPEN"
    s.position_ticket = int(getattr(match, "ticket", 0) or 0)
    s.open_price = float(getattr(match, "price_open", 0.0) or s.entry)
    return True


async def run_watcher(state: BotState) -> None:
    while True:
        await asyncio.sleep(getattr(CFG, "WATCHER_INTERVAL_SEC", 5))
        now = time.time()
        tick = mt5c.tick()

        constraints = mt5c.stop_constraints()
        min_dist = _min_stop_distance()

        open_positions = mt5c.positions_by_magic()

        for msg_id, splits in state.items():
            for s in splits:
                # ---------- PENDING maintenance ----------
                if s.status == "PENDING" and s.order_ticket:
                    ord_obj = mt5c.orders_get(s.order_ticket)
                    if ord_obj is None:
                        if _try_attach_filled_position(s, open_positions):
                            logger.log(
                                {
                                    "event": "PENDING_FILLED_DETECTED",
                                    "signal_msg_id": msg_id,
                                    "split": s.split_index,
                                    "order_ticket": s.order_ticket,
                                    "position_ticket": s.position_ticket,
                                    "open_price": s.open_price,
                                }
                            )
                        else:
                            logger.log(
                                {
                                    "event": "PENDING_DISAPPEARED_UNMATCHED",
                                    "signal_msg_id": msg_id,
                                    "split": s.split_index,
                                    "order_ticket": s.order_ticket,
                                }
                            )

                    if s.status == "PENDING":
                        inferred_side = "BUY" if s.entry < s.tp else "SELL"
                        age_s = now - s.created_ts

                        if tp_reached(inferred_side, s.tp, tick.bid, tick.ask):
                            req, res = mt5c.cancel_order(s.order_ticket)
                            s.status = "CANCELED"
                            logger.log(
                                {
                                    "event": "PENDING_CANCELED_TP",
                                    "signal_msg_id": msg_id,
                                    "split": s.split_index,
                                    "ticket": s.order_ticket,
                                    "inferred_side": inferred_side,
                                    "tp": s.tp,
                                    "bid": tick.bid,
                                    "ask": tick.ask,
                                    "age_s": age_s,
                                    "result": str(res),
                                }
                            )
                        elif age_s > CFG.PENDING_TIMEOUT_MIN * 60:
                            req, res = mt5c.cancel_order(s.order_ticket)
                            s.status = "CANCELED"
                            logger.log(
                                {
                                    "event": "PENDING_CANCELED_TIMEOUT",
                                    "signal_msg_id": msg_id,
                                    "split": s.split_index,
                                    "ticket": s.order_ticket,
                                    "inferred_side": inferred_side,
                                    "tp": s.tp,
                                    "bid": tick.bid,
                                    "ask": tick.ask,
                                    "age_s": age_s,
                                    "result": str(res),
                                }
                            )

                # ---------- BE pending/apply (OPEN only) ----------
                if s.status == "OPEN" and s.position_ticket and s.be_armed and not s.be_done:
                    be_price = s.open_price
                    if be_price is None:
                        pos = mt5c.position_get(s.position_ticket)
                        be_price = float(getattr(pos, "price_open", 0.0) or s.entry) if pos else s.entry
                        s.open_price = be_price

                    be_price = mt5c.normalize_price(float(be_price))
                    s.be_attempts += 1

                    allowed = _be_allowed(s.side, be_price, float(tick.bid), float(tick.ask), min_dist)

                    logger.log(
                        {
                            "event": "BE_APPLY_ATTEMPT",
                            "signal_msg_id": msg_id,
                            "split": s.split_index,
                            "ticket": s.position_ticket,
                            "side": s.side,
                            "be_price": be_price,
                            "bid": tick.bid,
                            "ask": tick.ask,
                            "min_stop_distance": min_dist,
                            "constraints": constraints,
                            "allowed": allowed,
                            "attempt": s.be_attempts,
                        }
                    )

                    if allowed:
                        req, res = mt5c.modify_sl(s.position_ticket, be_price)
                        if res and res.retcode == 10009:
                            s.be_done = True
                            s.be_armed = False
                            s.be_applied_ts = time.time()
                            logger.log(
                                {
                                    "event": "BE_APPLIED",
                                    "signal_msg_id": msg_id,
                                    "split": s.split_index,
                                    "ticket": s.position_ticket,
                                    "be_price": be_price,
                                    "result": str(res),
                                }
                            )
                        else:
                            logger.log(
                                {
                                    "event": "BE_APPLY_FAILED",
                                    "signal_msg_id": msg_id,
                                    "split": s.split_index,
                                    "ticket": s.position_ticket,
                                    "be_price": be_price,
                                    "result": str(res),
                                }
                            )

                # ---------- CLOSE_AT pending/apply (OPEN only) ----------
                if s.status == "OPEN" and s.position_ticket and s.close_armed and not s.close_done and s.close_target is not None:
                    s.close_attempts += 1
                    trig = _close_at_triggered(s.side, float(s.close_target), float(tick.bid), float(tick.ask))

                    logger.log(
                        {
                            "event": "CLOSE_AT_CHECK",
                            "signal_msg_id": msg_id,
                            "split": s.split_index,
                            "ticket": s.position_ticket,
                            "side": s.side,
                            "target": s.close_target,
                            "bid": tick.bid,
                            "ask": tick.ask,
                            "triggered": trig,
                            "attempt": s.close_attempts,
                        }
                    )

                    if trig:
                        req, res = mt5c.close_position(s.position_ticket, s.side, CFG.VOLUME)
                        if res and res.retcode == 10009:
                            s.close_done = True
                            s.close_armed = False
                            s.close_applied_ts = time.time()
                            s.status = "CLOSED"
                            logger.log(
                                {
                                    "event": "CLOSE_AT_APPLIED",
                                    "signal_msg_id": msg_id,
                                    "split": s.split_index,
                                    "ticket": s.position_ticket,
                                    "target": s.close_target,
                                    "result": str(res),
                                }
                            )
                        else:
                            logger.log(
                                {
                                    "event": "CLOSE_AT_FAILED",
                                    "signal_msg_id": msg_id,
                                    "split": s.split_index,
                                    "ticket": s.position_ticket,
                                    "target": s.close_target,
                                    "result": str(res),
                                }
                            )
