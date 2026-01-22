# core/watcher.py
import time
import asyncio
import config as CFG
from core import logger
from core.rules import tp_reached, min_stop_distance, be_allowed, close_at_triggered
from adapters import mt5_client as mt5c
from core.state import BotState


def _try_attach_filled_position(msg_id: int, split) -> bool:
    """
    Detecta si un pending order ya se convirtió en posición abierta.
    En tu broker/demo: order_ticket == position_ticket cuando se llena.
    """
    if not split.order_ticket:
        return False

    pos = mt5c.position_get(split.order_ticket)
    if not pos:
        return False

    split.position_ticket = split.order_ticket
    split.status = "OPEN"
    split.open_price = float(getattr(pos, "price_open", 0.0) or split.entry)

    # --- LOG extra para auditar TP/SL reales al fill ---
    tp_now = float(getattr(pos, "tp", 0.0) or 0.0)
    sl_now = float(getattr(pos, "sl", 0.0) or 0.0)

    logger.log_event(
        {
            "event": "PENDING_FILLED_DETECTED",
            "signal_msg_id": msg_id,
            "split": split.split_index,
            "order_ticket": split.order_ticket,
            "position_ticket": split.position_ticket,
            "open_price": split.open_price,
            "tp_pos": tp_now,
            "sl_pos": sl_now,
            "tp_expected": float(split.tp),
            "sl_expected": float(split.sl),
        }
    )

    # --- FIX: si el broker llena sin TP, lo restauramos inmediatamente ---
    if tp_now <= 0.0 and float(split.tp) > 0.0:
        req2, res2 = mt5c.modify_sltp(split.position_ticket, new_sl=float(split.sl), new_tp=float(split.tp))
        logger.log_event(
            {
                "event": "TP_RESTORE_AFTER_FILL",
                "signal_msg_id": msg_id,
                "split": split.split_index,
                "ticket": split.position_ticket,
                "tp_sent": float(split.tp),
                "sl_sent": float(split.sl),
                "result": str(res2),
            }
        )

    return True


async def run_watcher(state: BotState):
    while True:
        try:
            await _run_once(state)
        except Exception as e:
            # nunca dejamos morir al watcher
            logger.log_event({"event": "WATCHER_ERROR", "error": repr(e)})
        await asyncio.sleep(float(getattr(CFG, "WATCHER_INTERVAL_SEC", 1.0) or 1.0))


async def _run_once(state: BotState):
    tick = mt5c.symbol_tick()
    if not tick:
        return

    constraints = mt5c.symbol_constraints()
    min_dist = min_stop_distance(constraints, float(getattr(CFG, "BE_EXTRA_BUFFER", 0.0) or 0.0))

    now = time.time()
    vol = float(getattr(CFG, "VOLUME_PER_ORDER", 0.01) or 0.01)

    for msg_id, mem in state.signals.items():
        for s in mem.splits:
            # ---------- Pending management ----------
            if s.status == "PENDING" and s.order_ticket:
                if _try_attach_filled_position(msg_id, s):
                    pass
                else:
                    inferred_side = "BUY" if s.entry < s.tp else "SELL"
                    age_s = now - (getattr(s, "created_ts", now) or now)

                    if tp_reached(inferred_side, s.tp, tick.bid, tick.ask):
                        req, res = mt5c.cancel_order(s.order_ticket)
                        s.status = "CANCELED"
                        logger.log_event(
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
                    elif age_s > float(getattr(CFG, "PENDING_TIMEOUT_MIN", 10) or 10) * 60.0:
                        req, res = mt5c.cancel_order(s.order_ticket)
                        s.status = "CANCELED"
                        logger.log_event(
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

                allowed = be_allowed(s.side, be_price, float(tick.bid), float(tick.ask), min_dist)

                logger.log_event(
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
                    pos_now = mt5c.position_get(s.position_ticket)
                    tp_now = float(getattr(pos_now, "tp", 0.0) or 0.0) if pos_now else 0.0
                    tp_fallback = float(s.tp) if getattr(s, "tp", None) is not None else 0.0

                    req, res = mt5c.modify_sl(
                        s.position_ticket,
                        be_price,
                        fallback_tp=(tp_now if tp_now > 0.0 else tp_fallback),
                    )

                    if res and getattr(res, "retcode", None) == 10009:
                        s.be_done = True
                        s.be_armed = False
                        s.be_applied_ts = time.time()
                        logger.log_event(
                            {
                                "event": "BE_APPLIED",
                                "signal_msg_id": msg_id,
                                "split": s.split_index,
                                "ticket": s.position_ticket,
                                "be_price": be_price,
                                "tp_sent": float(req.get("tp", 0.0) or 0.0),
                                "result": str(res),
                            }
                        )
                    else:
                        logger.log_event(
                            {
                                "event": "BE_APPLY_FAILED",
                                "signal_msg_id": msg_id,
                                "split": s.split_index,
                                "ticket": s.position_ticket,
                                "be_price": be_price,
                                "tp_sent": float(req.get("tp", 0.0) or 0.0),
                                "result": str(res),
                            }
                        )

            # ---------- CLOSE_AT pending/apply (OPEN only) ----------
            if s.status == "OPEN" and s.position_ticket and s.close_armed and not s.close_done and s.close_target is not None:
                s.close_attempts += 1
                trig = close_at_triggered(
                    s.side,
                    float(s.close_target),
                    float(tick.bid),
                    float(tick.ask),
                    buffer=float(getattr(CFG, "CLOSE_AT_BUFFER", 0.0) or 0.0),
                )

                logger.log_event(
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
                    req, res = mt5c.close_position(s.position_ticket, s.side, vol)
                    if res and getattr(res, "retcode", None) == 10009:
                        s.close_done = True
                        s.close_armed = False
                        s.close_applied_ts = time.time()
                        s.status = "CLOSED"
                        logger.log_event(
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
                        logger.log_event(
                            {
                                "event": "CLOSE_AT_FAILED",
                                "signal_msg_id": msg_id,
                                "split": s.split_index,
                                "ticket": s.position_ticket,
                                "target": s.close_target,
                                "result": str(res),
                            }
                        )


