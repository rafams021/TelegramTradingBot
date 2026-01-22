import time
import config as CFG
from core import logger
from core.parser import parse_signal
from core.rules import decide_execution
from core.management import classify_management
from core.utils import safe_text_sample

from adapters import mt5_client as mt5c
from core.state import BotState


async def handle_signal(state: BotState, msg_id: int, text: str):
    sig = parse_signal(text)
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

    # Guardrail duro: demasiado lejos => no abrimos nada
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

    # Create signal state
    state.add_signal(msg_id, sig)

    # Splits by numeric TPs only (ignore "open")
    splits = state.build_splits_for_signal(msg_id)

    # Execute each split
    for s in splits:
        if s.tp is None:
            logger.log(
                {
                    "event": "SPLIT_SKIPPED_NO_TP",
                    "signal_msg_id": msg_id,
                    "split": s.split_index,
                }
            )
            s.status = "SKIPPED"
            continue

        if mode == "MARKET":
            req, res = mt5c.open_market(sig.side, CFG.VOLUME, sl=s.sl, tp=s.tp)
            s.status = "OPEN" if (res and res.retcode == 10009) else "FAILED"
            if res and res.retcode == 10009:
                s.position_ticket = int(res.order)
                s.open_price = float(getattr(res, "price", 0.0) or sig.entry)
            logger.log(
                {
                    "event": "OPEN_MARKET",
                    "signal_msg_id": msg_id,
                    "split": s.split_index,
                    "side": sig.side,
                    "entry": sig.entry,
                    "sl": s.sl,
                    "tp": s.tp,
                    "result": str(res),
                }
            )

        else:  # LIMIT
            req, res = mt5c.open_pending(sig.side, "LIMIT", CFG.VOLUME, price=s.entry, sl=s.sl, tp=s.tp)
            s.status = "PENDING" if (res and res.retcode == 10009) else "FAILED"
            if res and res.retcode == 10009:
                s.order_ticket = int(res.order)
            logger.log(
                {
                    "event": "OPEN_PENDING",
                    "signal_msg_id": msg_id,
                    "split": s.split_index,
                    "side": sig.side,
                    "entry": sig.entry,
                    "sl": s.sl,
                    "tp": s.tp,
                    "mode": "LIMIT",
                    "result": str(res),
                }
            )




