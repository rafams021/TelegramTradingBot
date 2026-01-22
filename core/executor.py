# core/executor.py
from __future__ import annotations

from typing import Optional

import config as CFG
from adapters import mt5_client as mt5c

from core import logger
from core.management import classify_management, apply_management
from core.parser import parse_signal
from core.rules import decide_execution
from core.state import BOT_STATE, BotState


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
        return float(bid) >= float(tp)
    return float(ask) <= float(tp)


async def execute_signal(
    msg_id: int,
    text: str,
    reply_to: Optional[int],
    date_iso: Optional[str] = None,
    is_edit: bool = False,
    state: BotState = BOT_STATE,
) -> None:
    """
    Telegram handler: recibe msg_id/text/reply_to y decide:
      - si es management (BE/CLOSE...) => aplica a state
      - si es signal => parsea, decide MARKET/LIMIT/SKIP, abre splits en MT5, guarda state y loggea

    Nota: Esta función ES async porque main.py la await-ea, pero internamente todo lo que hace es sync.
    """
    text = text or ""

    # --- 0) Management messages (BE / CLOSE...) ---
    mg = classify_management(text)
    if mg.kind != "NONE":
        apply_management(state=state, msg_id=msg_id, reply_to=reply_to, mg=mg)
        return

    # --- 1) Cache de mensajes para re-procesar edits (typos etc.) ---
    cache = state.upsert_msg_cache(msg_id=msg_id, text=text)

    # Si ya existe señal para este msg_id y no es edit, ignoramos duplicados
    if state.has_signal(msg_id) and not is_edit:
        logger.log_event(
            {
                "event": "SIGNAL_DUPLICATE_IGNORED",
                "msg_id": msg_id,
                "date": date_iso,
            }
        )
        return

    # Si es edit pero fuera de ventana o demasiados intentos, no reprocesar
    if is_edit:
        if not cache.within_edit_window(int(getattr(CFG, "TG_EDIT_REPROCESS_WINDOW_S", 180))):
            logger.log_event(
                {
                    "event": "EDIT_IGNORED_OUTSIDE_WINDOW",
                    "msg_id": msg_id,
                    "date": date_iso,
                    "first_seen_ts": cache.first_seen_ts,
                    "last_seen_ts": cache.last_seen_ts,
                    "window_s": int(getattr(CFG, "TG_EDIT_REPROCESS_WINDOW_S", 180)),
                }
            )
            return
        if cache.parse_attempts >= int(getattr(CFG, "TG_EDIT_REPROCESS_MAX_ATTEMPTS", 3)):
            logger.log_event(
                {
                    "event": "EDIT_IGNORED_MAX_ATTEMPTS",
                    "msg_id": msg_id,
                    "date": date_iso,
                    "attempts": cache.parse_attempts,
                    "max": int(getattr(CFG, "TG_EDIT_REPROCESS_MAX_ATTEMPTS", 3)),
                }
            )
            return

    # --- 2) Parse Signal ---
    sig = parse_signal(msg_id=msg_id, text=text)
    state.mark_parse_attempt(msg_id=msg_id, parse_failed=(sig is None))

    if sig is None:
        logger.log_event(
            {
                "event": "SIGNAL_PARSE_FAILED",
                "msg_id": msg_id,
                "reply_to": reply_to,
                "date": date_iso,
                "is_edit": is_edit,
                "text": text,
                "attempts": state.msg_cache.get(msg_id).parse_attempts if state.msg_cache.get(msg_id) else None,
            }
        )
        return

    logger.log_event(
        {
            "event": "SIGNAL_PARSED",
            "msg_id": msg_id,
            "reply_to": reply_to,
            "date": date_iso,
            "side": sig.side,
            "entry": sig.entry,
            "sl": sig.sl,
            "tps": list(sig.tps),
            "is_edit": is_edit,
        }
    )

    # --- 3) MT5 tick actual ---
    tick = mt5c.symbol_tick()
    if not tick:
        logger.log_event({"event": "MT5_TICK_MISSING", "msg_id": msg_id})
        return

    bid = float(tick.bid)
    ask = float(tick.ask)
    current_price = _current_price_for_side(sig.side, bid, ask)

    # --- 4) Decide ejecución ---
    mode = decide_execution(
        side=sig.side,
        entry=float(sig.entry),
        current_price=float(current_price),
    )

    logger.log_event(
        {
            "event": "EXECUTION_DECIDED",
            "msg_id": msg_id,
            "side": sig.side,
            "entry": sig.entry,
            "bid": bid,
            "ask": ask,
            "current_price": current_price,
            "delta": current_price - float(sig.entry),
            "mode": mode,
            "hard_drift": float(getattr(CFG, "HARD_DRIFT", 0.0) or 0.0),
            "buy_up_tol": float(getattr(CFG, "BUY_UP_TOL", 0.0) or 0.0),
            "buy_down_tol": float(getattr(CFG, "BUY_DOWN_TOL", 0.0) or 0.0),
            "sell_up_tol": float(getattr(CFG, "SELL_UP_TOL", 0.0) or 0.0),
            "sell_down_tol": float(getattr(CFG, "SELL_DOWN_TOL", 0.0) or 0.0),
        }
    )

    if mode == "SKIP":
        logger.log_event(
            {
                "event": "SIGNAL_SKIPPED_HARD_DRIFT",
                "msg_id": msg_id,
                "side": sig.side,
                "entry": sig.entry,
                "current_price": current_price,
            }
        )
        return

    # --- 5) Guardar señal en state + construir splits ---
    # (Si ya estaba agregada por un edit anterior, add_signal lo ignora.)
    state.add_signal(sig)
    splits = state.build_splits_for_signal(sig.message_id)

    # --- 6) Enviar órdenes por split ---
    vol = float(getattr(CFG, "VOLUME_PER_ORDER", 0.01) or 0.01)

    for sp in splits:
        # sp: core.state.SplitState
        tp = float(sp.tp)

        if _maybe_skip_if_tp_already_reached(sig.side, tp, bid, ask):
            sp.status = "CANCELED"
            logger.log_event(
                {
                    "event": "SPLIT_SKIPPED_TP_REACHED",
                    "signal_msg_id": msg_id,
                    "split": sp.split_index,
                    "tp": tp,
                    "bid": bid,
                    "ask": ask,
                }
            )
            continue

        if mode == "MARKET":
            req, res = mt5c.open_market(side=sig.side, volume=vol, sl=float(sig.sl), tp=tp)
            open_evt = "OPEN_MARKET"
        else:
            # Para ahora: pending usando LIMIT/STOP tal cual mode (rules puede devolver LIMIT)
            req, res = mt5c.open_pending(side=sig.side, mode=mode, volume=vol, price=float(sig.entry), sl=float(sig.sl), tp=tp)
            open_evt = "OPEN_PENDING"

        logger.log_event(
            {
                "event": open_evt,
                "signal_msg_id": msg_id,
                "split": sp.split_index,
                "side": sig.side,
                "entry": float(sig.entry),
                "sl": float(sig.sl),
                "tp": tp,
                "mode": mode,
                "request": req,
                "result": str(res),
            }
        )

        if res is None:
            # DRY_RUN
            sp.status = "DRY_RUN"
            continue

        ret = int(getattr(res, "retcode", 0) or 0)

        if ret == 10009:
            if open_evt == "OPEN_PENDING":
                sp.status = "PENDING"
                sp.order_ticket = int(getattr(res, "order", 0) or 0)
                sp.position_ticket = None
                sp.open_price = None
            else:
                sp.status = "OPEN"
                # En DEAL, MetaTrader5 suele devolver position en "order" o "deal" dependiendo broker.
                # Tu watcher asume position_ticket == order_ticket en filled market también; aquí guardamos el "order" por consistencia.
                sp.position_ticket = int(getattr(res, "order", 0) or 0)
                sp.order_ticket = None
                sp.open_price = float(getattr(res, "price", 0.0) or 0.0)
        else:
            sp.status = "OPEN_FAILED"
            logger.log_event(
                {
                    "event": "OPEN_FAILED",
                    "signal_msg_id": msg_id,
                    "split": sp.split_index,
                    "retcode": ret,
                    "comment": str(getattr(res, "comment", "")),
                    "result": str(res),
                }
            )
