import config as CFG
from core import logger
from core.parser import parse_signal
from core.rules import decide_execution
from core.utils import safe_text_sample

from adapters import mt5_client as mt5c
from core.state import BotState


async def handle_signal(state: BotState, msg_id: int, text: str):
    sig = parse_signal(text, msg_id)  # <-- FIX: ahora pasa msg_id
    if not sig:
        logger.log(
            {
                "event": "SIGNAL_PARSE_FAILED",
                "msg_id": msg_id,
                "text": safe_text_sample(text, 600),
            }
        )
        return

    logger.log(
        {
            "event": "SIGNAL_PARSED",
            "msg_id": msg_id,
            "side": sig.side,
            "entry": sig.entry,
            "sl": sig.sl,
            "tps": sig.tps,
        }
    )

    tick = mt5c.symbol_tick()
    if not tick:
        logger.log({"event": "NO_TICK", "msg_id": msg_id})
        return

    current_price = float(tick.ask) if sig.side == "BUY" else float(tick.bid)
    mode = decide_execution(sig.side, sig.entry, current_price)
    delta = current_price - float(sig.entry)

    logger.log(
        {
            "event": "EXECUTION_DECIDED",
            "msg_id": msg_id,
            "side": sig.side,
            "entry": sig.entry,
            "bid": tick.bid,
            "ask": tick.ask,
            "current_price": current_price,
            "delta": delta,
            "mode": mode,
            "hard_drift": getattr(CFG, "HARD_DRIFT", None),
            "buy_up_tol": getattr(CFG, "BUY_UP_TOL", None),
            "buy_down_tol": getattr(CFG, "BUY_DOWN_TOL", None),
            "sell_up_tol": getattr(CFG, "SELL_UP_TOL", None),
            "sell_down_tol": getattr(CFG, "SELL_DOWN_TOL", None),
        }
    )

    if mode == "SKIP":
        logger.log(
            {
                "event": "SIGNAL_SKIPPED_HARD_DRIFT",
                "msg_id": msg_id,
                "side": sig.side,
                "entry": sig.entry,
                "current_price": current_price,
                "delta": delta,
            }
        )
        return

    # Persist state + build splits (SL default y MAX_SPLITS viven en state)
    state.add_signal(msg_id, sig)
    splits = state.build_splits_for_signal(msg_id)

    for s in splits:
        if mode == "MARKET":
            req, res = mt5c.open_market(s.side, CFG.VOLUME, sl=s.sl, tp=s.tp)
            s.status = "OPEN" if (res and res.retcode == 10009) else "FAILED"
            if res and res.retcode == 10009:
                # OJO: en MT5, res.order suele ser ticket de la posición (depende broker),
                # tu watcher ya hace attach para pending; aquí solo guardamos algo útil.
                s.position_ticket = int(res.order)
                s.open_price = float(getattr(res, "price", 0.0) or s.entry)

            logger.log(
                {
                    "event": "OPEN_MARKET",
                    "signal_msg_id": msg_id,
                    "split": s.split_index,
                    "side": s.side,
                    "entry": s.entry,
                    "sl": s.sl,
                    "tp": s.tp,
                    "result": str(res),
                }
            )
        else:
            req, res = mt5c.open_pending(s.side, "LIMIT", CFG.VOLUME, price=s.entry, sl=s.sl, tp=s.tp)
            s.status = "PENDING" if (res and res.retcode == 10009) else "FAILED"
            if res and res.retcode == 10009:
                s.order_ticket = int(res.order)

            logger.log(
                {
                    "event": "OPEN_PENDING",
                    "signal_msg_id": msg_id,
                    "split": s.split_index,
                    "side": s.side,
                    "entry": s.entry,
                    "sl": s.sl,
                    "tp": s.tp,
                    "mode": "LIMIT",
                    "result": str(res),
                }
            )





