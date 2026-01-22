# core/executor.py

from __future__ import annotations

from dataclasses import asdict
from typing import Optional, Tuple

import config as CFG
from core.logger import log_event
from core.models import Signal
from core import rules
from core.state import BOT_STATE, SplitState
from core import mt5_client as mt5c


def _current_price_for_side(side: str, bid: float, ask: float) -> float:
    side_u = (side or "").upper().strip()
    return float(ask) if side_u == "BUY" else float(bid)


def _maybe_skip_if_tp_already_reached(side: str, tp: float, bid: float, ask: float) -> bool:
    """
    Si el TP ya fue tocado al momento de procesar, no abrimos split.
    BUY: si bid >= tp
    SELL: si ask <= tp
    """
    side_u = (side or "").upper().strip()
    if side_u == "BUY":
        return bid >= tp
    return ask <= tp


def _send_order(
    mode: str,
    side: str,
    volume: float,
    entry: float,
    sl: float,
    tp: float,
) -> Tuple[Optional[dict], Optional[object]]:
    """
    Centraliza envíos a MT5 (market vs pending).
    """
    mode_u = (mode or "").upper().strip()
    if mode_u == "MARKET":
        return mt5c.open_market(side=side, volume=volume, sl=sl, tp=tp)
    # Por default todo lo NO-MARKET lo tratamos como pending LIMIT (o STOP si tu lógica lo decide arriba)
    return mt5c.open_pending(side=side, mode=mode_u, volume=volume, price=entry, sl=sl, tp=tp)


def execute_signal(signal: Signal) -> None:
    """
    Esta es la función que main.py importa.
    Recibe Signal YA parseada.
    """
    # 1) Guardar estado de señal
    BOT_STATE.register_signal(signal)

    # 2) Tick actual
    tick = mt5c.symbol_tick()
    if not tick:
        log_event({"event": "MT5_TICK_MISSING", "signal_msg_id": signal.msg_id})
        return

    bid = float(tick.bid)
    ask = float(tick.ask)
    current_price = _current_price_for_side(signal.side, bid, ask)

    # 3) Decidir MARKET vs LIMIT usando drift tolerances
    mode = rules.decide_execution(
        side=signal.side,
        entry=signal.entry,
        current_price=current_price,
    )

    log_event(
        {
            "event": "EXECUTION_DECIDED",
            "msg_id": signal.msg_id,
            "side": signal.side,
            "entry": signal.entry,
            "bid": bid,
            "ask": ask,
            "current_price": current_price,
            "delta": current_price - signal.entry,
            "mode": mode,
            "hard_drift": getattr(CFG, "HARD_DRIFT", None),
            "buy_up_tol": getattr(CFG, "BUY_UP_TOL", None),
            "buy_down_tol": getattr(CFG, "BUY_DOWN_TOL", None),
            "sell_up_tol": getattr(CFG, "SELL_UP_TOL", None),
            "sell_down_tol": getattr(CFG, "SELL_DOWN_TOL", None),
        }
    )

    # 4) Crear splits y enviar órdenes
    #    Nota: “TP open” ya viene filtrado en parser (tps numéricos).
    if not signal.tps:
        log_event(
            {
                "event": "SIGNAL_NO_TPS",
                "msg_id": signal.msg_id,
                "text": getattr(signal, "raw_text", ""),
            }
        )
        return

    for i, tp in enumerate(signal.tps):
        # regla: si TP ya tocado al momento de procesar -> skip
        if _maybe_skip_if_tp_already_reached(signal.side, tp, bid, ask):
            log_event({"event": "SPLIT_SKIPPED_TP_REACHED", "signal_msg_id": signal.msg_id, "split": i, "tp": tp})
            continue

        split = SplitState(
            split=i,
            side=signal.side,
            entry=signal.entry,
            sl=signal.sl,
            tp=tp,
            volume=float(signal.volume),
            status="NEW",
        )
        # referencia del signal (para BE y closes por reply_to)
        split.signal_msg_id = signal.msg_id  # dinámico, no rompe dataclass

        req, res = _send_order(
            mode=mode,
            side=signal.side,
            volume=float(signal.volume),
            entry=signal.entry,
            sl=signal.sl,
            tp=tp,
        )

        # log del open
        open_evt = "OPEN_MARKET" if (mode or "").upper().strip() == "MARKET" else "OPEN_PENDING"
        log_event(
            {
                "event": open_evt,
                "signal_msg_id": signal.msg_id,
                "split": i,
                "side": signal.side,
                "entry": signal.entry,
                "sl": signal.sl,
                "tp": tp,
                "mode": mode,
                "request": req,
                "result": str(res),
            }
        )

        # actualizar estado split
        if res is None:
            split.status = "DRY_RUN"
        else:
            ret = int(getattr(res, "retcode", 0) or 0)
            if ret == 10009:  # DONE
                if open_evt == "OPEN_PENDING":
                    split.status = "PENDING"
                    split.order_ticket = int(getattr(res, "order", 0) or 0)
                else:
                    split.status = "OPEN"
                    split.position_ticket = int(getattr(res, "order", 0) or 0)
                    split.open_price = float(getattr(res, "price", 0.0) or 0.0)
            else:
                split.status = "OPEN_FAILED"
                split.fail_retcode = ret
                split.fail_comment = str(getattr(res, "comment", ""))

        BOT_STATE.register_split(signal.msg_id, split)



