# core/watcher.py
import time

import config as CFG
from adapters.mt5_client import MT5Client, Tick
from core.logger import Logger
from core.rules import tp_reached, min_stop_distance, be_allowed, close_at_triggered
from core.state import State


def infer_side_from_signal(entry: float, tp: float) -> str:
    """Heurística por si no tenemos side guardado. Para XAUUSD típicamente TP>entry => BUY."""
    return "BUY" if float(tp) > float(entry) else "SELL"


def watch_pending_orders(mt5c: MT5Client, state: State, logger: Logger, symbol: str, poll_s: float = 1.0) -> None:
    while True:
        tick = mt5c.get_tick(symbol)
        if not tick:
            time.sleep(poll_s)
            continue

        for msg_id, sig_state in list(state.signals.items()):
            for s in sig_state.splits:
                if s.status != "PENDING" or not s.order_ticket:
                    continue

                order = mt5c.order_get(s.order_ticket)
                if not order:
                    # Could have been filled/removed; try to find position
                    pos = mt5c.position_find_by_magic_or_comment(msg_id, s.split_index)
                    if pos:
                        s.status = "OPEN"
                        s.position_ticket = getattr(pos, "ticket", None)
                        s.open_price = float(getattr(pos, "price_open", 0.0) or 0.0)
                        s.open_ts = time.time()
                        logger.log_event(
                            {
                                "event": "PENDING_FILLED_DETECTED",
                                "signal_msg_id": msg_id,
                                "split": s.split_index,
                                "ticket": s.order_ticket,
                                "position_ticket": s.position_ticket,
                                "open_price": s.open_price,
                                "ts": time.time(),
                            }
                        )
                    continue

                # Cancel if TP already reached (avoid late fills after TP)
                inferred_side = s.side or infer_side_from_signal(s.entry, s.tp)
                if tp_reached(inferred_side, s.tp, float(tick.bid), float(tick.ask)):
                    age_s = time.time() - float(s.pending_created_ts or time.time())
                    req, res = mt5c.cancel_order(s.order_ticket)
                    s.status = "CANCELED"
                    logger.log_event(
                        {
                            "event": "PENDING_CANCELED_TP_REACHED",
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
                else:
                    # Optional: timeout cancel
                    age_s = time.time() - float(s.pending_created_ts or time.time())
                    if age_s > float(getattr(CFG, "PENDING_TIMEOUT_MIN", 10) or 10) * 60.0:
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

        time.sleep(poll_s)


def watch_open_positions(mt5c: MT5Client, state: State, logger: Logger, symbol: str, poll_s: float = 1.0) -> None:
    """Applies BE/CLOSE_AT management rules to OPEN positions."""
    constraints = mt5c.symbol_constraints(symbol)
    min_dist = min_stop_distance(constraints, extra_buffer=float(getattr(CFG, "STOP_EXTRA_BUFFER", 0.0) or 0.0))
    vol = float(getattr(CFG, "DEFAULT_LOT", 0.01))

    while True:
        tick = mt5c.get_tick(symbol)
        if not tick:
            time.sleep(poll_s)
            continue

        for msg_id, sig_state in list(state.signals.items()):
            for s in sig_state.splits:

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

                # ---------- MOVE_SL pending/apply (OPEN only) ----------
                if (
                    s.status == "OPEN"
                    and s.position_ticket
                    and getattr(s, "sl_move_armed", False)
                    and not getattr(s, "sl_move_done", False)
                    and getattr(s, "sl", None) is not None
                ):
                    s.sl_move_attempts += 1
                    desired_sl = mt5c.normalize_price(float(s.sl))

                    pos_now = mt5c.position_get(s.position_ticket)
                    if not pos_now:
                        logger.log_event(
                            {
                                "event": "MOVE_SL_NO_POSITION",
                                "signal_msg_id": msg_id,
                                "split": s.split_index,
                                "ticket": s.position_ticket,
                                "desired_sl": desired_sl,
                                "attempt": s.sl_move_attempts,
                            }
                        )
                    else:
                        tp_now = float(getattr(pos_now, "tp", 0.0) or 0.0)
                        sl_now = float(getattr(pos_now, "sl", 0.0) or 0.0)
                        logger.log_event(
                            {
                                "event": "MOVE_SL_APPLY_ATTEMPT",
                                "signal_msg_id": msg_id,
                                "split": s.split_index,
                                "ticket": s.position_ticket,
                                "sl_now": sl_now,
                                "desired_sl": desired_sl,
                                "tp_now": tp_now,
                                "attempt": s.sl_move_attempts,
                            }
                        )

                        req, res = mt5c.modify_sltp(s.position_ticket, new_sl=desired_sl, new_tp=tp_now)
                        if res and getattr(res, "retcode", None) == 10009:
                            s.sl_move_done = True
                            s.sl_move_armed = False
                            s.sl_move_applied_ts = time.time()
                            logger.log_event(
                                {
                                    "event": "MOVE_SL_APPLIED",
                                    "signal_msg_id": msg_id,
                                    "split": s.split_index,
                                    "ticket": s.position_ticket,
                                    "desired_sl": desired_sl,
                                    "tp_sent": float(req.get("tp", 0.0) or 0.0),
                                    "result": str(res),
                                }
                            )
                        else:
                            logger.log_event(
                                {
                                    "event": "MOVE_SL_APPLY_FAILED",
                                    "signal_msg_id": msg_id,
                                    "split": s.split_index,
                                    "ticket": s.position_ticket,
                                    "desired_sl": desired_sl,
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

        time.sleep(poll_s)


